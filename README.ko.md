<div align="center">

<img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

</div>

# ref-verify

[한국어](https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md) | [English](https://github.com/Moonweave-Research/ref-verify/blob/main/README.md)

**제출 전에 참고문헌 목록을 점검해, 존재하지 않거나 다른 논문을 가리키거나 철회된 참고문헌을 찾아냅니다.**

AI 도우미가 만들어 준 참고문헌 목록이나 이전 원고에서 옮겨 온 목록에는 실제로 없는 논문,
다른 논문의 DOI, 철회된 논문이 섞여 들어가기 쉽습니다. ref-verify는 참고문헌을 하나씩
CrossRef와 대조해 어떤 항목을 다시 봐야 하는지 알려 줍니다.

- **누가 쓰나요:** 논문, 학위논문, 연구계획서를 마무리하는 연구자와 대학원생, 그리고 이들을 돕는 AI 도우미.
- **무엇을 얻나요:** 참고문헌마다 판정(`PASS`, `WARN`, `REJECT`, `UNVERIFIED`)과 그 이유. 터미널, JSON, HTML 보고서 중에서 고를 수 있습니다.
- **어떻게 쓰나요:** 연구 인용 검증용 에이전트 스킬(Claude Code, Cursor, Codex)이나 명령줄 도구로 씁니다. 서버를 시작하거나 MCP를 설정할 필요가 없습니다. 계정이나 API 키도 필요 없습니다.

---

## 30초 만에 써 보기

Python 3.10 이상이 필요합니다.

```bash
pipx install ref-verify            # 설치 없이 바로: uvx ref-verify check-bib ...
curl -O https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/examples/references.txt
ref-verify check-bib references.txt
```

[`examples/references.txt`](https://github.com/Moonweave-Research/ref-verify/blob/main/examples/references.txt)에는
참고문헌 7개가 들어 있습니다. 각 항목 위 주석에 실제로 어떤 문헌인지 적어 두었습니다. 진짜 논문 3개,
연도를 잘못 쓴 진짜 논문 1개, 지어낸 참고문헌 1개, 철회된 논문 1개, CrossRef에 없는 국내
박사학위논문 1개입니다. 아래는 ref-verify 1.3.1을 실행한 결과 그대로입니다.

```text
7 references: 3 PASS, 1 WARN, 2 REJECT, 1 UNVERIFIED

VERDICT     REFERENCE                                   DOI
PASS        1. Pelrine, R., Kornbluh, R., Pei, Q., &…   10.1126/science.287.5454.836
PASS        2. Watts, D. J., & Strogatz, S. H. (1998)…  10.1038/30918 (resolved)
PASS        3. 김가은 (2024). IPA 분석을 통한 프로스…   10.5392/jkca.2024.24.09.361
WARN        4. Hochreiter, S., & Schmidhuber, J. (199…  10.1162/neco.1997.9.8.1735
            DOI matches, but the year differs (reference: 1999; CrossRef: 1997).
REJECT      5. Pelrine, R., Kornbluh, R., & Pei, Q. (…  10.1002/adma.200390974
            CrossRef has no record for this DOI (HTTP 404), and doi.org does not list it either.
REJECT      6. Wakefield, A. J., Murch, S. H., Anthon…  10.1016/s0140-6736(97)11096-0
            CrossRef records this paper as retracted (notice DOI 10.1016/s0140-6736(10)60175-4); do
            not use it as a source.
UNVERIFIED  7. 강동휘 (2025). 폴리(비닐피리딘) 기반…    -
            No matching CrossRef record was found; verify this reference manually.

PASS: matches CrossRef. WARN: check the difference named under it. REJECT: dead DOI, a different
paper, or retracted. UNVERIFIED: could not be confirmed automatically; that alone does not mean the
reference is wrong.
```

모든 항목이 통과하지는 않았으므로 종료 코드는 `2`입니다. CrossRef 데이터는 계속 바뀌므로 나중에
실행하면 결과가 조금 다를 수 있습니다. 내 목록을 점검하려면 Zotero, EndNote, Mendeley에서
BibTeX이나 RIS로 내보내거나, 목록을 복사해 `.txt` 파일로 저장한 뒤
`ref-verify check-bib <파일>`을 실행합니다.

---

## 결과 읽는 법

| 판정 | 뜻 | 할 일 |
|---|---|---|
| `PASS` | DOI의 CrossRef 기록(DOI가 없으면 검색으로 찾은 기록)과 제목, 제1저자, 연도가 일치합니다. | 없음. |
| `WARN` | 찾기는 했지만 무언가 다릅니다. 바로 아래 줄에 연도, 제1저자, 또는 그 DOI가 실제로 가리키는 논문 제목이 나옵니다. | 그 항목만 원문과 대조합니다. |
| `REJECT` | DOI가 어디에도 없거나, 다른 논문의 DOI이거나, 철회된 논문입니다. | 인용을 고치거나 뺍니다. |
| `UNVERIFIED` | 자동으로 확인하지 못했습니다. 틀렸다는 판정이 아닙니다. | 직접 찾아봅니다. |

`UNVERIFIED`는 주의해서 읽어야 합니다. DOI 없이 지어낸 참고문헌은 반박할 근거가 없으니
`REJECT`가 아니라 `UNVERIFIED`로만 나옵니다. CrossRef에 없는 진짜 학위논문, KCI 논문, 책,
프리프린트도 똑같이 `UNVERIFIED`로 나옵니다. 직접 만든 시험 세트 세 개를 ref-verify 1.3.1로
2026-10-09에 돌렸을 때 `UNVERIFIED`는 다음과 같았습니다.

| 시험 세트 | `UNVERIFIED` | 지어낸 것 | CrossRef에 없는 정상 문헌 | CrossRef에 없는 철회 논문 | 진짜 논문 |
|---|---|---|---|---|---|
| [홀드아웃 세트 v2](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-holdout-v2.json) | 29 | 13 | 12 | 3 | 1 |
| [홀드아웃 세트 v1](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-holdout-v1.json) | 22 | 14 | 8 | 0 | 0 |
| [개발 세트](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-v1.json) | 31 | 15 | 16 | 0 | 0 |
| 합계 | 82 | 42 | 36 | 3 | 1 |

대략 절반은 가짜, 절반은 정상 문헌이었다는 뜻이니 `UNVERIFIED` 항목은 Google Scholar, RISS,
KCI에서 한 번씩 직접 찾아보세요. 이 비율은 시험 세트의 구성에서 나온 것이라 실제 참고문헌 목록의
비율과는 다릅니다.

---

## 세 가지 사용 방법

### 에이전트 스킬로

```bash
# Node.js에 포함된 npx 필요
npx skills add Moonweave-Research/ref-verify -g \
  --skill ref-verify \
  --agent claude-code cursor codex \
  -y
```

설치한 뒤 에이전트에게 평소 말투로 요청하면 됩니다.

```text
references.bib 참고문헌 전체를 ref-verify로 점검해줘
```

스킬 안에 명령줄 엔진이 함께 들어 있고 `python3`(3.10 이상)로 실행하므로 따로 설치할 것이
없습니다. Python 패키지는 CLI 전용이라 `SKILL.md`를 설치하지 않습니다. 에이전트 스킬은 위 명령으로 GitHub에서 설치합니다.
다른 요청 예시는 [에이전트 스킬](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md#에이전트-스킬)에 있습니다.

### 명령줄에서

| 명령 | 확인하는 것 |
|---|---|
| `ref-verify check-bib references.bib` | 참고문헌 목록: BibTeX, RIS, 일반 텍스트·Markdown(`.txt`, `.md`) |
| `ref-verify verify-doi <doi> --title "..." --first-author <성> --year <연도>` | DOI 하나를 내가 적은 제목, 제1저자, 연도와 대조 |
| `ref-verify check-claim <doi> --claim "..."` | 논문 초록에 특정 숫자나 문구가 명시되어 있는지 |
| `ref-verify check-file claims.jsonl` | DOI와 주장 쌍 여러 개를 한 번에(JSONL 또는 CSV) |

프로그램에서 읽을 출력이 필요하면 `--json`을 붙입니다. 모든 명령, 옵션, 오류 코드는
[명령줄 엔진](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md#명령줄-엔진)에 있습니다.

### 저장한 보고서로

```bash
ref-verify check-bib references.bib --report report.html
```

지도교수나 공동 저자에게 보낼 수 있는 HTML 파일 하나가 만들어집니다. 맨 위에 판정별 개수가
나오고 확인이 필요한 참고문헌이 먼저 정리됩니다. DOI에는 `https://doi.org/` 링크만 붙이고 다른
외부 자원은 불러오지 않습니다. Markdown으로 받으려면 `--report report.md`를 씁니다. 자세한 내용은
[저장한 보고서](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md#저장한-보고서)에 있습니다.

---

## 채점표

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/scorecard-dark.svg">
  <img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/scorecard-light.svg" alt="홀드아웃 세트 v2 참고문헌 99개에 대한 check-bib 판정 막대 그래프: 진짜 논문 89% 통과, 지어낸 참고문헌 100% 잡음, CrossRef가 기록한 철회 8건 중 8건 잡음, CrossRef에 없는 정상 문헌 13개 중 0개 REJECT." width="830">
</picture>

홀드아웃(held-out) 세트 v2는 도구를 돌리기 전에 작성하고 커밋해 둔 참고문헌 99개입니다. 앞선
세트들과 겹치는 논문은 없습니다. 2026-10-09에 ref-verify 1.3.1로 실제 CrossRef에 조회해 한 번
측정했습니다.

| 측정 항목 (홀드아웃 세트 v2) | 결과 | n | 95% 신뢰구간 |
|---|---|---|---|
| 진짜 논문을 깨끗이 통과시킴(`PASS`) | **89%** (40) | 45 | 77–95% |
| 진짜 논문을 확인 필요로 보냄(`WARN`) | 11% (5) | 45 | 5–23% |
| 진짜 논문을 틀렸다고 판정함(`REJECT`) | 0% (0) | 45 | 0–8% |
| 지어낸 참고문헌을 잡음(`WARN` 또는 `REJECT`) | **100%** (29) | 29 | 88–100% |
| CrossRef가 기록한 철회를 `PAPER_RETRACTED`로 잡음 | **100%** (8) | 8 | 68–100% |
| CrossRef에 없는 정상 문헌을 틀렸다고 판정함 | 0% (0) | 13 | 0–23% |

- 지어낸 참고문헌 유형별: 가짜 DOI 6/6, DOI 없음 6/6, 다른 논문의 DOI 5/5, 저자·연도 틀림 5/5, 공개 보고된 사례 7/7.
- `WARN`으로 간 진짜 논문 5건: 학술지 약어를 쓴 제목 없는 인용 1건, 단체 저자 인용 2건, 무관한 기록에 연결된 1건, 인쇄 연도로 인용한 책 1건.
- 이 밖에 Retraction Watch에는 철회로 올라 있지만 CrossRef가 표시할 수 없는 철회 4건이 있습니다(DOI가 KISTI, ISTIC, DataCite에 등록됐거나, 학회 초록의 DOI가 철회 공지로 연결되는 경우). 4건 모두 `PAPER_RETRACTED`를 받지 못했습니다. 3건은 `UNVERIFIED`, 1건은 다른 논문으로 보아 `REJECT`였습니다.
- CrossRef에 없는 책 1건(Feynman Lectures)은 같은 제목의 1964년 학술지 서평에 연결되어 통과했습니다.
- 99개 전체 시간: 캐시 없이 97초(참고문헌당 중앙값 1.1초), 캐시 사용 시 0.1초.
- 표본 내 세트(도구를 고칠 때 이미 써서 점수가 실제보다 좋게 나옴): 홀드아웃 세트 v1(86개) 진짜 40/40 `PASS`, 가짜 26/26 잡음, 철회 10/10, CrossRef 미등재 문헌 0/10 REJECT. 개발 세트(142개) 진짜 66/66, 가짜 43/43, 철회 16/16, CrossRef 미등재 문헌 1/17 REJECT.

방법: 각 세트를 BibTeX, RIS, 일반 텍스트 목록으로 `check-bib`에 넣고 빈 캐시에서 실행했습니다.
항목별 판정은 결과 파일([홀드아웃 세트 v2](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/results/2026-10-09-8170e66-holdout-v2.json))에
모두 남겼습니다. 측정하지 않은 것: 논문이 주장을 뒷받침하는지(작은 수치 fixture 외), 한국어를 뺀
영어 외 문헌, 본문. 데이터셋, 방법, 재실행 방법은
[benchmarks/README.md](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/README.md)에 있습니다.

---

## 확인하는 것과 확인하지 않는 것

| 질문 | 확인 여부 | 방법 |
|---|---|---|
| DOI가 실제로 있는가? | 예 | CrossRef에서 찾고 없으면 doi.org에서 다른 등록기관(arXiv·Zenodo의 DataCite, KISTI 등)의 DOI인지 확인합니다. 그런 DOI는 없는 DOI가 아니라 `UNVERIFIED`입니다. |
| 제목, 제1저자, 연도가 DOI와 맞는가? | 예 | CrossRef 기록과 비교합니다. |
| DOI 없는 참고문헌이 실재하는가? | 일부 | CrossRef에 색인돼 있으면 검색으로 찾습니다. 색인돼 있지 않으면 `REJECT`가 아니라 `UNVERIFIED`입니다. |
| 철회된 논문인가? | CrossRef에 기록이 있을 때 | CrossRef의 철회 공지로 판단합니다. CrossRef가 담고 있는 Retraction Watch 데이터도 포함됩니다. CrossRef에 없는 논문의 철회는 놓칩니다. |
| 초록에 특정 숫자나 문구가 있는가? | 예, 초록만 | `check-claim`, `check-file`. 초록은 CrossRef, OpenAlex, Semantic Scholar, PubMed에서 가져옵니다. |
| 본문, 그림, 표, 보충자료 | 아니요 | |
| p-value, AUC, odds ratio 같은 통계 | 아니요 | 스킬의 수동 절차에 맡깁니다. |
| 논문의 질, 새로움, 학계 합의 | 아니요 | |

범위에 대한 자세한 설명은 [범위](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md#범위--선택적-cli와-수동-감사의-경계)에 있습니다.

---

## 개인정보와 네트워크

ref-verify는 외부 Python 패키지(third-party Python runtime dependency)가 없지만 오프라인으로 돌지는
않습니다. 공개 학술 API로 outbound HTTPS 요청을 보낼 수 있어야 합니다. 연결하는 곳은 CrossRef, OpenAlex, Semantic Scholar, PubMed, doi.org뿐입니다.

| 서비스 | 언제 | 보내는 것 |
|---|---|---|
| CrossRef (`api.crossref.org`) | 모든 명령 | DOI, 또는 DOI가 없는 참고문헌이면 참고문헌 문장 자체를 검색어로 |
| doi.org | CrossRef에 DOI 기록이 없을 때 | DOI |
| OpenAlex, Semantic Scholar, PubMed(NCBI) | `check-claim`, `check-file`에서 CrossRef에 초록이 없을 때 | DOI(arXiv DOI는 Semantic Scholar에 arXiv ID로) |

- 파일이나 주장 문장을 어딘가에 올리지 않습니다. 주장과 초록의 비교는 내 컴퓨터에서 하고, 위에 없는 서비스로는 아무것도 보내지 않습니다.
- 모든 요청에는 `ref-verify/<버전> (+https://github.com/Moonweave-Research/ref-verify)` user agent가 붙습니다. 이메일 주소는 `REF_VERIFY_MAILTO`를 설정했을 때만 CrossRef에 보냅니다. OpenAlex 요청에는 `REF_VERIFY_OPENALEX_MAILTO`가 붙고, 기본값은 임시 주소(`verify@ref-verify.local`)입니다. Semantic Scholar 키는 `SEMANTIC_SCHOLAR_API_KEY`를 설정했을 때만 보냅니다.
- 응답은 디스크에 7일(찾지 못한 DOI는 1일) 캐시합니다. 위치는 `$REF_VERIFY_CACHE_DIR`, 없으면 `$XDG_CACHE_HOME/ref-verify`, 그것도 없으면 `~/.cache/ref-verify`입니다. 캐시 파일에는 요청 URL(DOI나 참고문헌 문장이 들어 있음)과 응답이 남습니다.
- `--no-cache`나 `REF_VERIFY_NO_CACHE=1`로 캐시를 끄고, 그 폴더를 지우면 비워집니다. 자세한 내용은 [캐시](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md#캐시)에 있습니다.

---

## AI 에이전트를 위한 안내

AI 도우미가 ref-verify를 제대로 호출하는 데 필요한 사항입니다. 전체 계약은
[AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md), 스킬 지침은
[SKILL.md](https://github.com/Moonweave-Research/ref-verify/blob/main/SKILL.md)에 있습니다.

**명령**

```bash
ref-verify check-bib references.bib --json     # 참고문헌 목록
ref-verify check-file claims.jsonl --json      # DOI와 주장 쌍
ref-verify verify-doi <doi> --title "..." --first-author <성> --year <연도> --json
ref-verify check-claim <doi> --claim "..." --json
# 설치된 스킬 안에서는 함께 들어 있는 엔진을 실행:
PYTHONPATH="$SKILL_DIR/src" python3 -m ref_verify.cli check-bib references.bib --json
```

**종료 코드**

| 코드 | 뜻 |
|---|---|
| `0` | 모든 항목이 `PASS`(`check-bib`, `verify-doi`)이거나 `ACCEPT`(`check-claim`, `check-file`). |
| `2` | 실행은 끝났지만 통과하지 못한 항목이 있음. 그래도 JSON은 읽어야 합니다. |
| `1` | 입력이나 실행 오류. |

- **입력:** `check-bib`은 `.bib`, `.ris`, `.txt`, `.md`(다른 확장자면 `--format bib|ris|txt`). `check-file`은 `{"doi": ..., "claim": ..., "id": ..., "note": ...}` 형식의 JSONL 행(`doi`, `claim`은 필수).
- **중요한 JSON 키:** `summary`(`check-bib`은 `total`, `pass`, `warn`, `reject`, `unverified`, `failed`)와 결과마다 `verdict`, `status`, `error_code`, `resolved_doi`, `mismatches`, `reason`.
- **확인된 것으로 보고하면 안 되는 결과:** `check-bib`의 `WARN`, `REJECT`, `UNVERIFIED`. 주장 확인의 `WARN`, `PARTIAL`, `REJECT`, `UNVERIFIABLE`. `failed > 0`인 실행. 참고문헌은 `PASS`, 주장은 `ACCEPT`만 확인된 것으로 봅니다.
- **표현:** `REFERENCE_UNMATCHED`는 CrossRef 검색에서 일치하는 기록을 찾지 못했다는 뜻입니다. 확인되지 않았다고 알리고 사용자에게 확인을 부탁하되, 지어냈다고 말하지 않습니다. `DOI_NOT_IN_CROSSREF`는 다른 등록기관의 DOI라는 뜻이며 없는 DOI가 아닙니다. `REFERENCE_RESOLVED`이면 `resolved_doi`를 그 참고문헌의 DOI로 씁니다.
- **하지 말 것:** 초록이 없을 때 기억으로 채우지 않습니다. 초록만 확인했으면서 본문, 표, 그림까지 뒷받침된다고 하지 않습니다.

---

## 더 자세한 문서

- [docs/REFERENCE.ko.md](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md): 모든 명령, 모드, 오류 코드, 캐시, 범위, 예시.
- [AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md): CLI를 호출하는 에이전트를 위한 계약(영어).
- [SKILL.md](https://github.com/Moonweave-Research/ref-verify/blob/main/SKILL.md): 에이전트 스킬 본문(영어).
- [benchmarks/README.md](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/README.md): 시험 세트와 재실행 방법(영어).
- [CHANGELOG.md](https://github.com/Moonweave-Research/ref-verify/blob/main/CHANGELOG.md): 릴리스별 변경 사항(영어).

---

## 기여, 라이선스, 관련 프로젝트

- 이슈와 풀 리퀘스트를 환영합니다. 변경을 보내기 전에 `PYTHONPATH=src python3 -m unittest discover -s tests`로 테스트를 돌려 주세요.
- 라이선스: [MIT](https://github.com/Moonweave-Research/ref-verify/blob/main/LICENSE).
- 관련 프로젝트: [decision-kernel](https://github.com/Moonweave-Systems/decision-kernel). 코딩 에이전트를 위한 근거 기반 결정, 작업 이탈 점검, 완료 점검 스킬 모음입니다.
