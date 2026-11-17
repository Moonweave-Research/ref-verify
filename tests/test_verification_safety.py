import io
import json
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from urllib.error import HTTPError, URLError

from ref_verify.claim_check import check_claim_support
from ref_verify.cli import main
from ref_verify.models import PaperRecord
from ref_verify.reference_parse import ReferenceEntry
from ref_verify.reference_resolve import check_reference


PAPER = PaperRecord('10.1000/example', 'Test', ['Smith'], 2020,
                    'Treatment improves survival.', 'CrossRef')


class AgencyClient:
    def __init__(self, agency=None, error=None):
        self.agency = agency
        self.error = error

    def fetch_work(self, doi):
        raise HTTPError('https://api.crossref.org/works/x', 404, 'Not Found', None, None)

    def registration_agency(self, doi):
        if self.error:
            raise self.error
        return self.agency


class MetadataClient:
    def __init__(self, record=PAPER, error=None):
        self.record = record
        self.error = error

    def fetch_work(self, doi):
        if self.error:
            raise self.error
        return self.record


class AbstractClient:
    source_name = 'openalex'

    def fetch_record(self, doi):
        return replace(PAPER, source='OpenAlex')


def run_cli(args, client, abstract_clients=()):
    output = io.StringIO()
    with redirect_stdout(output):
        code = main([*args, '--json', '--no-cache'], client=client, abstract_clients=abstract_clients)
    return code, json.loads(output.getvalue())


class VerificationSafetyTests(unittest.TestCase):
    def test_negative_and_uncertain_evidence_never_accepts_positive_claim(self):
        for abstract, claim in [
            ('No evidence that treatment improves survival.', 'Treatment improves survival.'),
            ('There is no evidence that treatment improves survival.', 'Treatment improves survival.'),
            ('It is unlikely that treatment improves survival.', 'Treatment improves survival.'),
            ('There is insufficient evidence that treatment improves survival.', 'Treatment improves survival.'),
            ('There is no convincing clinical evidence that treatment improves survival.', 'Treatment improves survival.'),
            ('Evidence that treatment improves survival is lacking.', 'Treatment improves survival.'),
            ('The hypothesis that treatment improves survival was rejected.', 'Treatment improves survival.'),
            ('No evidence that the device reaches 5 V.', 'The device reaches 5 V.'),
            ('We cannot conclude that the device reaches 5 V.', 'The device reaches 5 V.'),
            ('The device cannot reach 5 V.', 'The device reaches 5 V.'),
            ('There is no evidence that actuation strain exceeds 100%.', 'Actuation strain exceeds 100%.'),
        ]:
            with self.subTest(abstract=abstract):
                self.assertEqual(check_claim_support(replace(PAPER, abstract=abstract), claim).verdict, 'WARN')

    def test_independent_positive_evidence_stays_supported(self):
        for abstract, claim in [
            ('No evidence of toxicity was found. Treatment improves survival.', 'Treatment improves survival.'),
            ('No evidence of failure was found. The device reaches 5 V.', 'The device reaches 5 V.'),
            ('Actuation strain reached no less than 117%.', 'actuation strain above 100%'),
        ]:
            with self.subTest(abstract=abstract):
                self.assertEqual(check_claim_support(replace(PAPER, abstract=abstract), claim).verdict, 'ACCEPT')

    def test_agency_outage_is_unverified_for_all_cli_paths(self):
        for error in [URLError('timed out'), HTTPError('https://doi.org/ra/x', 429, 'rate limited', None, None),
                      HTTPError('https://doi.org/ra/x', 503, 'unavailable', None, None)]:
            client = AgencyClient(error=error)
            for args in [['verify-doi', PAPER.doi], ['check-claim', PAPER.doi, '--claim', PAPER.abstract]]:
                with self.subTest(error=error, command=args[0]):
                    code, payload = run_cli(args, client)
                    self.assertEqual(code, 2)
                    self.assertEqual(payload['verdict'], 'WARN')
                    self.assertEqual(payload['error_code'], 'REGISTRATION_LOOKUP_FAILED')
            entry = ReferenceEntry(index=1, key=None, raw=PAPER.doi, title=None, first_author=None, year=None, doi=PAPER.doi, journal=None)
            result = check_reference(entry, client)
            self.assertEqual(result.verdict, 'WARN')
            self.assertEqual(result.status, 'UNVERIFIED')
            self.assertEqual(result.error_code, 'REGISTRATION_LOOKUP_FAILED')

    def test_confirmed_absence_and_other_registration_agency_remain_distinct(self):
        for agency, verdict, error_code in [(None, 'REJECT', 'DOI_NOT_FOUND'),
                                             ('DataCite', 'WARN', 'DOI_NOT_IN_CROSSREF')]:
            with self.subTest(agency=agency):
                _, payload = run_cli(['verify-doi', PAPER.doi], AgencyClient(agency=agency))
                self.assertEqual(payload['verdict'], verdict)
                self.assertEqual(payload['error_code'], error_code)

    def test_explicit_abstract_source_keeps_retraction_and_identity_checks(self):
        for record, error_code in [(replace(PAPER, retraction_doi='10.1000/notice'), 'PAPER_RETRACTED'),
                                   (replace(PAPER, doi='10.1000/other'), 'DOI_MISMATCH')]:
            with self.subTest(error_code=error_code):
                _, payload = run_cli(['check-claim', PAPER.doi, '--claim', PAPER.abstract, '--source', 'openalex'],
                                     MetadataClient(record), [AbstractClient()])
                self.assertNotEqual(payload['verdict'], 'ACCEPT')
                self.assertEqual(payload['error_code'], error_code)

    def test_explicit_source_accepts_when_metadata_and_evidence_are_available(self):
        code, payload = run_cli(['check-claim', PAPER.doi, '--claim', PAPER.abstract, '--source', 'openalex'],
                                MetadataClient(), [AbstractClient()])
        self.assertEqual(code, 0)
        self.assertEqual(payload['verdict'], 'ACCEPT')
        self.assertEqual(payload['abstract_source'], 'openalex')

    def test_source_error_is_not_hidden_by_unavailable_retraction_metadata(self):
        class WrongDoi(AbstractClient):
            def fetch_record(self, doi):
                return replace(PAPER, doi='10.1000/other')

        for sources, expected in [([], 'NO_ABSTRACT'), ([WrongDoi()], 'DOI_MISMATCH')]:
            with self.subTest(expected=expected):
                _, payload = run_cli(['check-claim', PAPER.doi, '--claim', PAPER.abstract, '--source', 'openalex'],
                                     MetadataClient(error=URLError('unavailable')), sources)
                self.assertEqual(payload['verdict'], 'WARN')
                self.assertEqual(payload['error_code'], expected)
                self.assertEqual(payload['retraction_check'], 'UNAVAILABLE')

    def test_explicit_source_preserves_evidence_but_warns_if_retraction_check_fails(self):
        code, payload = run_cli(['check-claim', PAPER.doi, '--claim', PAPER.abstract, '--source', 'openalex'],
                                MetadataClient(error=URLError('CrossRef unavailable')), [AbstractClient()])
        self.assertEqual(code, 2)
        self.assertEqual(payload['verdict'], 'WARN')
        self.assertEqual(payload['error_code'], 'RETRACTION_CHECK_UNAVAILABLE')
        self.assertEqual(payload['abstract_source'], 'openalex')
        self.assertEqual(payload['evidence'], PAPER.abstract)


if __name__ == '__main__':
    unittest.main()
