import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from ref_verify.abstract_lookup import AbstractSourceError
from ref_verify.cache import ResponseCache, cache_directory, default_cache
from ref_verify.cli import main
from ref_verify.crossref import CrossrefClient
from ref_verify.http import fetch_json, fetch_text
from ref_verify.openalex import OpenAlexClient
from ref_verify.pubmed import PubMedClient

URL = "https://api.example.test/works/10.1000%2Fexample"


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body.encode("utf-8")


def _http_error(code, retry_after=None):
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return HTTPError(url=URL, code=code, msg="error", hdrs=headers, fp=None)


class FakeClock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


class ResponseCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.cache = ResponseCache(Path(self.tmp.name), ttl_seconds=100, clock=self.clock)

    def test_miss_then_hit(self):
        self.assertIsNone(self.cache.get(URL))

        self.cache.put(URL, 200, '{"ok": true}')
        entry = self.cache.get(URL)

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.status, 200)
        self.assertEqual(entry.body, '{"ok": true}')

    def test_entry_expires_after_ttl(self):
        self.cache.put(URL, 200, "{}")

        self.clock.now += 99
        self.assertIsNotNone(self.cache.get(URL))
        self.clock.now += 2
        self.assertIsNone(self.cache.get(URL))

    def test_not_found_entry_uses_shorter_ttl(self):
        cache = ResponseCache(
            Path(self.tmp.name),
            ttl_seconds=7 * 86400,
            not_found_ttl_seconds=86400,
            clock=self.clock,
        )
        cache.put(URL, 404, "")

        self.clock.now += 86400 - 1
        self.assertEqual(cache.get(URL).status, 404)
        self.clock.now += 2
        self.assertIsNone(cache.get(URL))

    def test_corrupt_entry_is_a_miss(self):
        self.cache.put(URL, 200, "{}")
        for path in Path(self.tmp.name).glob("*.json"):
            path.write_text("{not json", encoding="utf-8")

        self.assertIsNone(self.cache.get(URL))

    def test_entry_for_another_url_is_a_miss(self):
        self.cache.put(URL, 200, "{}")
        for path in Path(self.tmp.name).glob("*.json"):
            entry = json.loads(path.read_text(encoding="utf-8"))
            entry["url"] = "https://other.test/"
            path.write_text(json.dumps(entry), encoding="utf-8")

        self.assertIsNone(self.cache.get(URL))

    def test_write_failure_is_swallowed(self):
        blocker = Path(self.tmp.name) / "file"
        blocker.write_text("", encoding="utf-8")
        cache = ResponseCache(blocker / "cache", ttl_seconds=100)

        cache.put(URL, 200, "{}")

        self.assertIsNone(cache.get(URL))


class CacheConfigTests(unittest.TestCase):
    def test_directory_precedence(self):
        with patch.dict(
            os.environ,
            {"REF_VERIFY_CACHE_DIR": "/tmp/rv-explicit", "XDG_CACHE_HOME": "/tmp/xdg"},
        ):
            self.assertEqual(cache_directory(), Path("/tmp/rv-explicit"))
        with patch.dict(os.environ, {"XDG_CACHE_HOME": "/tmp/xdg"}):
            os.environ.pop("REF_VERIFY_CACHE_DIR", None)
            self.assertEqual(cache_directory(), Path("/tmp/xdg/ref-verify"))
        with patch.dict(os.environ, {}):
            os.environ.pop("REF_VERIFY_CACHE_DIR", None)
            os.environ.pop("XDG_CACHE_HOME", None)
            self.assertEqual(cache_directory(), Path.home() / ".cache" / "ref-verify")

    def test_no_cache_env_disables_default_cache(self):
        with patch.dict(os.environ, {"REF_VERIFY_NO_CACHE": "1"}):
            self.assertIsNone(default_cache())
        with patch.dict(os.environ, {"REF_VERIFY_NO_CACHE": "0", "REF_VERIFY_CACHE_DIR": "/tmp/rv"}):
            self.assertIsNotNone(default_cache())

    def test_ttl_days_env(self):
        with patch.dict(os.environ, {"REF_VERIFY_CACHE_TTL_DAYS": "2", "REF_VERIFY_CACHE_DIR": "/tmp/rv"}):
            os.environ.pop("REF_VERIFY_NO_CACHE", None)
            cache = default_cache()
        assert cache is not None
        self.assertEqual(cache.ttl_seconds, 2 * 86400)
        with patch.dict(os.environ, {"REF_VERIFY_CACHE_TTL_DAYS": "soon", "REF_VERIFY_CACHE_DIR": "/tmp/rv"}):
            os.environ.pop("REF_VERIFY_NO_CACHE", None)
            cache = default_cache()
        assert cache is not None
        self.assertEqual(cache.ttl_seconds, 7 * 86400)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.sleeps = []

    def _fetch(self, **kwargs):
        return fetch_json(URL, headers={}, timeout=1.0, sleep=self.sleeps.append, **kwargs)

    def test_retries_429_then_succeeds(self):
        with patch("ref_verify.http.urlopen", side_effect=[_http_error(429), _Response('{"ok": 1}')]) as urlopen:
            payload = self._fetch()

        self.assertEqual(payload, {"ok": 1})
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(len(self.sleeps), 1)

    def test_honours_retry_after_seconds(self):
        with patch(
            "ref_verify.http.urlopen",
            side_effect=[_http_error(503, retry_after="7"), _Response("{}")],
        ):
            self._fetch()

        self.assertEqual(self.sleeps, [7.0])

    def test_gives_up_when_retry_after_exceeds_cap(self):
        with patch(
            "ref_verify.http.urlopen",
            side_effect=[_http_error(429, retry_after="120"), _Response("{}")],
        ) as urlopen:
            with self.assertRaises(HTTPError) as context:
                self._fetch()

        self.assertEqual(context.exception.code, 429)
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(self.sleeps, [])

    def test_backoff_is_exponential_and_capped(self):
        errors = [_http_error(500)] * 6
        with patch("ref_verify.http.urlopen", side_effect=errors) as urlopen:
            with self.assertRaises(HTTPError):
                self._fetch(max_retries=5)

        self.assertEqual(urlopen.call_count, 6)
        self.assertEqual(self.sleeps, [1.0, 2.0, 4.0, 8.0, 10.0])

    def test_404_is_not_retried(self):
        with patch("ref_verify.http.urlopen", side_effect=[_http_error(404), _Response("{}")]) as urlopen:
            with self.assertRaises(HTTPError) as context:
                self._fetch()

        self.assertEqual(context.exception.code, 404)
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(self.sleeps, [])

    def test_other_4xx_is_not_retried(self):
        with patch("ref_verify.http.urlopen", side_effect=[_http_error(400), _Response("{}")]) as urlopen:
            with self.assertRaises(HTTPError):
                self._fetch()

        self.assertEqual(urlopen.call_count, 1)

    def test_cache_hit_skips_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ResponseCache(Path(tmp), ttl_seconds=100)
            with patch("ref_verify.http.urlopen", side_effect=[_Response('{"n": 1}')]) as urlopen:
                first = self._fetch(cache=cache)
                second = self._fetch(cache=cache)

        self.assertEqual(first, {"n": 1})
        self.assertEqual(second, {"n": 1})
        self.assertEqual(urlopen.call_count, 1)

    def test_404_is_cached_as_negative_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ResponseCache(Path(tmp), ttl_seconds=100)
            with patch("ref_verify.http.urlopen", side_effect=[_http_error(404)]) as urlopen:
                for _ in range(2):
                    with self.assertRaises(HTTPError) as context:
                        self._fetch(cache=cache)
                    self.assertEqual(context.exception.code, 404)

        self.assertEqual(urlopen.call_count, 1)

    def test_server_errors_are_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = ResponseCache(Path(tmp), ttl_seconds=100)
            with patch("ref_verify.http.urlopen", side_effect=[_http_error(503)]):
                with self.assertRaises(HTTPError):
                    self._fetch(cache=cache, max_retries=0)

            self.assertIsNone(cache.get(URL))

    def test_fetch_text_returns_raw_body(self):
        with patch("ref_verify.http.urlopen", side_effect=[_Response("<xml/>")]):
            body = fetch_text(URL, headers={}, timeout=1.0)

        self.assertEqual(body, "<xml/>")



CROSSREF_BODY = json.dumps(
    {
        "message": {
            "DOI": "10.1000/example",
            "title": ["Cached paper"],
            "author": [{"family": "Lee"}],
            "issued": {"date-parts": [[2024]]},
        }
    }
)


class ClientRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = ResponseCache(Path(self.tmp.name), ttl_seconds=100)

    def test_crossref_client_reads_through_cache(self):
        client = CrossrefClient(timeout=1.0, cache=self.cache)
        with patch("ref_verify.http.urlopen", side_effect=[_Response(CROSSREF_BODY)]) as urlopen:
            first = client.fetch_work("10.1000/example")
            second = client.fetch_work("10.1000/example")

        self.assertEqual(first, second)
        self.assertEqual(second.title, "Cached paper")
        self.assertEqual(urlopen.call_count, 1)

    def test_openalex_cached_404_still_reports_not_found(self):
        client = OpenAlexClient(timeout=1.0, mailto="test@example.org", cache=self.cache)
        with patch("ref_verify.http.urlopen", side_effect=[_http_error(404)]) as urlopen:
            for _ in range(2):
                with self.assertRaises(AbstractSourceError) as context:
                    client.fetch_record("10.1000/missing")
                self.assertEqual(context.exception.status, "NOT_FOUND")

        self.assertEqual(urlopen.call_count, 1)

    def test_pubmed_fetches_search_json_then_article_xml(self):
        search = _Response(json.dumps({"esearchresult": {"idlist": ["12345"]}}))
        article = _Response(
            """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article>
<ArticleTitle>PubMed paper</ArticleTitle>
<Abstract><AbstractText>Samples were kept at 37 C.</AbstractText></Abstract>
</Article></MedlineCitation><PubmedData><ArticleIdList>
<ArticleId IdType="doi">10.1000/pubmed</ArticleId>
</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""
        )
        client = PubMedClient(timeout=1.0, cache=self.cache)
        with patch("ref_verify.http.urlopen", side_effect=[search, article]) as urlopen:
            first = client.fetch_record("10.1000/pubmed")
            second = client.fetch_record("10.1000/pubmed")

        self.assertEqual(first.abstract, "Samples were kept at 37 C.")
        self.assertEqual(first, second)
        self.assertEqual(urlopen.call_count, 2)


class CliCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"REF_VERIFY_CACHE_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("REF_VERIFY_NO_CACHE", None)

    def _run_twice(self, argv):
        responses = [_Response(CROSSREF_BODY), _Response(CROSSREF_BODY)]
        with patch("ref_verify.http.urlopen", side_effect=responses) as urlopen:
            for _ in range(2):
                with redirect_stdout(io.StringIO()):
                    main(argv)
        return urlopen.call_count

    def _cache_files(self):
        return list(Path(self.tmp.name).glob("*.json"))

    def test_cli_caches_responses_by_default(self):
        calls = self._run_twice(["verify-doi", "10.1000/example", "--title", "Cached paper", "--json"])

        self.assertEqual(calls, 1)
        self.assertEqual(len(self._cache_files()), 1)

    def test_no_cache_flag_before_subcommand(self):
        calls = self._run_twice(["--no-cache", "verify-doi", "10.1000/example", "--json"])

        self.assertEqual(calls, 2)
        self.assertEqual(self._cache_files(), [])

    def test_no_cache_flag_after_subcommand(self):
        calls = self._run_twice(["verify-doi", "10.1000/example", "--no-cache", "--json"])

        self.assertEqual(calls, 2)
        self.assertEqual(self._cache_files(), [])

    def test_no_cache_environment_variable(self):
        os.environ["REF_VERIFY_NO_CACHE"] = "1"

        calls = self._run_twice(["verify-doi", "10.1000/example", "--json"])

        self.assertEqual(calls, 2)
        self.assertEqual(self._cache_files(), [])


if __name__ == "__main__":
    unittest.main()
