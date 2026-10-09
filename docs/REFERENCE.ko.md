# ref-verify 참고 문서

[한국어](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md) | [English](https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md)

[README](https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md)에서 다루지 않은 세부
내용을 모았습니다. 모든 명령, 모드, 오류 코드, 캐시, 그리고 확인 범위의 한계를 설명합니다.
PyPI의 현재 릴리스인 ref-verify 1.3.2 기준입니다.

## 목차

- [에이전트 스킬](#에이전트-스킬)
- [참고문헌 목록 점검(check-bib)](#참고문헌-목록-점검check-bib)
- [명령줄 엔진](#명령줄-엔진)
- [모드](#모드)
- [오류 코드](#오류-코드)
- [저장한 보고서](#저장한-보고서)
- [캐시](#캐시)
- [범위 — 선택적 CLI와 수동 감사의 경계](#범위--선택적-cli와-수동-감사의-경계)
- [잡아내는 문제](#잡아내는-문제)
- [예시](#예시)
- [개발과 릴리스 점검](#개발과-릴리스-점검)

---

## 에이전트 스킬

`ref-verify`는 연구 인용 검증용 에이전트 스킬입니다. Claude Code,
Cursor, Codex 같은 스킬 지원 에이전트가 초안에 참고문헌을 넣기 전에
반복 가능한 검증 절차를 따르도록 합니다. 논문 찾기, DOI 확인, 특정 주장을 논문이 실제로
뒷받침하는지 확인, 제출 전 참고문헌 점검에 사용할 수 있습니다.

### 스킬 설치

```bash
# Node.js에 포함된 npx 필요
npx skills add Moonweave-Research/ref-verify -g \
  --skill ref-verify \
  --agent claude-code cursor codex \
  -y
```

**Claude Code, Cursor, Codex** 및 `npx skills` 생태계를 지원하는
에이전트에서 사용할 수 있습니다.

설치 후에는 일반 에이전트 스킬처럼 자연어로 요청하면 됩니다. 이
워크플로우에는 MCP 서버가 필요하지 않습니다. 서버를 시작하거나 MCP를
설정하지 않습니다.

스킬 안에 CLI 엔진이 함께 들어 있고 에이전트가 스킬 폴더에서 직접 실행하므로
따로 설치할 것이 없습니다. `python3`로 Python 3.10 이상을 실행할 수 있어야 합니다.

에이전트가 CLI를 호출할 때 따라야 할 명시적 규칙은
[AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md)를 참고하세요.

### 요청 예시

자연스럽게 요청하면 됩니다.

```text
제출 전에 이 인용들을 검증해줘: [DOI list]
이 논문이 "actuation strain above 100%"라는 주장을 실제로 뒷받침해?
claim X를 뒷받침하는 논문 3개를 찾고, 각 인용을 검증해줘
이 title/year와 DOI 10.1126/science.287.5454.836이 맞는지 확인해줘
제출 전에 참고문헌 전체를 점검해줘
references.bib 참고문헌 전체를 ref-verify로 점검해줘
```

일반 주제 설명, 문장 다듬기, APA/IEEE 형식 정리, 인용 스타일 질문에는
조용히 있습니다.

---

## 참고문헌 목록 점검(check-bib)

논문이나 학위논문의 참고문헌 중에 존재하지 않거나(ChatGPT가 지어낸 것 등), DOI가
다른 논문을 가리키거나, 철회된 논문이 섞여 있는지 한 번에 확인합니다.

**에이전트에게 맡길 때:** 스킬을 설치한 뒤 "references.bib 참고문헌 전체를
ref-verify로 점검해줘"라고 요청하면 됩니다.

**터미널에서 직접 할 때:**

1. 목록을 파일로 준비합니다.
   - Zotero: 컬렉션 우클릭 → 컬렉션 내보내기 → BibTeX → `references.bib`
     (EndNote·Mendeley는 BibTeX이나 RIS로 내보내기)
   - Word·한글 원고: 참고문헌 목록을 복사해 메모장 등에 붙여 넣고
     `references.txt`로 저장합니다. `[1]`, `1.` 번호나 줄바꿈이 있어도 됩니다.
     `.docx`, `.hwp`, `.pdf`는 직접 읽지 못합니다.
2. 설치합니다(Python 3.10 이상).

   ```bash
   pipx install ref-verify
   ```

   `uv`가 있다면 설치 없이 `uvx ref-verify check-bib references.bib`로
   바로 실행해도 됩니다.

3. 실행합니다.

   ```bash
   ref-verify check-bib references.bib
   ref-verify check-bib references.ris --json
   ref-verify check-bib references.md --format txt
   ```

   처음 실행할 때는 참고문헌 하나에 1초 정도 걸립니다(150개면 2분 남짓,
   `Checking references: 37/150`처럼 진행 상황이 보입니다). 같은 목록을 다시 돌리면
   캐시 덕분에 몇 초면 끝납니다. `REF_VERIFY_MAILTO=내이메일@학교.ac.kr`를 앞에
   붙이면 CrossRef의 polite pool을 써서 약 3배 빨라집니다.

   지도교수나 공동 저자에게 보낼 파일이 필요하면 `--report 점검결과.html`을 붙입니다.
   브라우저로 열면 확인이 필요한 항목이 맨 위에 모여 있습니다.

### check-bib이 참고문헌을 대조하는 방식

BibTeX, RIS, 일반 텍스트·Markdown 목록(문단마다, 줄마다, 또는
`[1]`/`1.`/`1)` 번호마다 참고문헌 하나)을 읽습니다. DOI가 있는 항목은
`verify-doi`처럼 CrossRef 기록과 대조하고, 일반 텍스트 항목은 본문에
CrossRef 제목과 제1저자가 드러날 때만 통과합니다. DOI가 없는 항목은
CrossRef 서지 검색으로 찾아 제목이 일치하고 연도 차이가 1년 이내일 때만
받아들입니다. 인쇄본 연도와 온라인 선공개 연도 모두, 부제나 판 표기를 뺀 제목,
BibTeX 제목의 TeX 수식(`$\beta$`는 β), CrossRef에
등록된 원어 제목(예: 『폴리머』 논문의 한글 제목), 한글 저자명과 CrossRef의 로마자
표기(윤 → Yoon/Yun)를 같은 것으로 봅니다. CrossRef에 없는 DOI는 doi.org에 등록기관을
물어보므로 arXiv, Zenodo, KISTI DOI를 없는 DOI로 판정하지 않습니다. 논문 자체가 아니라
그 논문에 관한 기록(동료 심사 보고서, Faculty Opinions 추천, addendum·correction)은 검색
결과에서 건너뜁니다.

논문 제목을 쓰지 않는 물리·화학 인용 형식(`J. Bardeen, L. N. Cooper, and
J. R. Schrieffer, Phys. Rev. 108, 1175 (1957)`)은 학술지(전체 이름 또는 약어), 권, 첫 쪽
또는 논문 번호, 연도, 제1저자로 비교하며, 모두 맞으면 통과하고 다르면 어느 항목이 다른지
이유에 적습니다. DOI가 없고 일반 검색에서 찾지 못했으며 제목 없는 인용으로 보이면 제1저자,
나머지 인용 정보, 인용 연도로 CrossRef를 한 번 더 검색해
`A. G. Riess et al., Astron. J. 116, 1009 (1998).` 같은 짧은 인용도 찾으며, 이때도 모든
항목이 일치해야 받아들입니다. 제1저자는 저자 목록의 첫 이름에서만 읽으므로 공저자를 맨 앞에 쓴
참고문헌은 통과하지 않습니다.

### 출력

터미널 출력은 `19 references: 11 PASS, 2 WARN, 5 REJECT, 1 UNVERIFIED` 같은 개수 줄로
시작하고, 참고문헌마다 한 줄(인용 키, 붙여 넣은 목록이면 참고문헌 앞부분)을 보여 주며, `PASS`가
아닌 줄 아래에는 이유를, 끝에는 판정 설명을 붙입니다. `--json`이면 `summary`(`total`, `pass`, `warn`,
`reject`, `unverified`, `failed`; `warn`에는 `UNVERIFIED` 항목도 포함)와 `results`를 담은 객체입니다.
모든 항목이 `PASS`일 때만 exit `0`입니다.

### check-bib 결과 읽는 법

| 결과 | 뜻 | 할 일 |
|---|---|---|
| `PASS` | DOI(또는 검색으로 찾은 기록)의 제목·제1저자·연도가 CrossRef와 일치 | 없음 |
| `WARN` | 찾았지만 무언가 다름. 바로 아래 줄에 무엇이 다른지 나옵니다(연도, 저자, DOI가 가리키는 다른 논문 제목 등) | 그 항목만 원문과 대조 |
| `REJECT` | DOI가 어디에도 없음, 전혀 다른 논문을 가리킴, 또는 철회된 논문 | 인용을 고치거나 빼기 |
| `UNVERIFIED` | 자동으로 확인하지 못함. 학위논문, 국내 학회 초록, 일부 책, CrossRef가 아닌 곳(arXiv, KISTI 등)에 등록된 DOI가 흔히 여기에 옵니다. 틀렸다는 뜻이 아닙니다 | 직접 확인 |

DOI가 없는 가짜 참고문헌은 `REJECT`가 아니라 `UNVERIFIED`로만 나올 수 있습니다.
`UNVERIFIED` 항목은 Google Scholar나 RISS에서 실제로 있는지 한 번씩 찾아보세요.

---

## 명령줄 엔진

스킬이 에이전트 워크플로우입니다. Python CLI는 설치된 스킬이 터미널에서
호출할 수 있는 skill-level execution engine입니다.

Python 패키지는 CLI 전용입니다. `SKILL.md`를 설치하지 않습니다. 에이전트
스킬은 위의 `npx skills add` 명령으로 GitHub에서 설치합니다.

이것은 스킬/플러그인 수준 워크플로우이며 MCP 서버가 아닙니다. CLI는
현재 직접 자동화해도 안전한 부분만 담당합니다.

- CrossRef 메타데이터 확인: `ref-verify verify-doi`
- DOI에 묶인 abstract 기반 주장 확인: `ref-verify check-claim`
- 여러 DOI 기반 주장 일괄 확인: `ref-verify check-file`
  - 문장 그대로 드러나는 text claim
  - efficiency, response rate, actuation strain 같은 subject가 일치하는 percentage claim
  - cycles, patients, voltage, temperature, concentration 같은 단순 unit/count claim
  - CrossRef를 먼저 쓰고, CrossRef에 abstract가 없으면 DOI가 일치하는 OpenAlex, Semantic Scholar, PubMed fallback 사용
- 참고문헌 목록 확인(BibTeX, RIS, 일반 텍스트, Markdown): `ref-verify check-bib`
- 에이전트가 읽기 쉬운 JSON 출력
- `WARN`, `REJECT`, `UNVERIFIABLE` 결과에 대한 non-zero exit code

`p-value`, AUC/AUROC, F1 score, hazard ratio, odds ratio, confidence interval
같은 통계 지표는 아직 수동 스킬 프로토콜을 따릅니다. DOI landing page 확인은 스킬 프로토콜을 따릅니다. Unpaywall, arXiv, 두 개 이상의 독립 출처로 존재 확인도 스킬 프로토콜이 담당합니다.
CrossRef가 철회 공지를 기록한 DOI는 CLI가 바로 `REJECT`합니다. CrossRef에 없는 철회 배너 확인은 여전히 `SKILL.md`의 스킬 프로토콜이 담당합니다.

CLI에는 third-party Python runtime dependency가 없지만, offline verifier는
아닙니다. 실제 검증에는 CrossRef, OpenAlex, Semantic Scholar, PubMed 같은 공개 학술
API로 outbound HTTPS 요청을 보낼 수 있어야 합니다.

### CLI 설치

CLI를 직접 쓰려면 PyPI에서 설치합니다.

```bash
uvx ref-verify --help            # 설치 없이 실행 (uv)
pipx install ref-verify          # 또는 `ref-verify` 명령 설치
```

로컬 체크아웃에서 설치할 수도 있습니다.

```bash
git clone https://github.com/Moonweave-Research/ref-verify.git
cd ref-verify
python3 -m pip install -e .
```

CLI 사용 가능 여부를 확인합니다.

```bash
ref-verify --help
```

설치하지 않은 소스 체크아웃에서는 모듈 엔트리포인트를 사용합니다.

```bash
PYTHONPATH=src python3 -m ref_verify.cli --help
```

DOI 메타데이터를 확인합니다.

```bash
ref-verify verify-doi 10.1126/science.287.5454.836 \
  --title "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%" \
  --first-author Pelrine \
  --year 2000 \
  --json
```

DOI에 묶인 abstract에 대해 특정 주장을 확인합니다.

```bash
ref-verify check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

기본값으로 `check-claim`은 CrossRef를 먼저 사용합니다. CrossRef에 abstract가 없으면 DOI가 일치하는 OpenAlex, Semantic Scholar, PubMed fallback을 시도합니다. 특정 소스만 디버깅하려면 `--source crossref`, `--source openalex`, `--source semantic-scholar`, `--source pubmed`를 사용합니다. 명시적으로 non-CrossRef 소스를 고르면 CrossRef를 거치지 않습니다.

소스 체크아웃에서 바로 실행하는 예시는 다음과 같습니다.

```bash
PYTHONPATH=src python3 -m ref_verify.cli verify-doi 10.1126/science.287.5454.836 \
  --title "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%" \
  --first-author Pelrine \
  --year 2000 \
  --json

PYTHONPATH=src python3 -m ref_verify.cli check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

---

## 모드

**Quick Screen**은 이미 DOI가 있을 때 사용합니다. CrossRef로 DOI, 제목,
첫 번째 저자의 성, 연도를 비교합니다.

```bash
ref-verify verify-doi <doi> --title "<title>" --first-author <last-name> --year <year> --json
```

`verify-doi`는 `PASS`일 때만 exit code `0`을 반환합니다. `WARN`과
`REJECT`는 non-zero exit code를 반환하므로, 약하거나 맞지 않는
메타데이터가 자동화 단계를 조용히 통과할 수 없습니다.

**Full Audit**은 논문을 처음 찾거나 제출 전 최종 점검을 할 때 사용합니다.
스킬은 필요한 경우 CrossRef, OpenAlex, Semantic Scholar, Unpaywall, arXiv, PubMed를
통해 source text를 가져옵니다. topline claim은 abstract에서 확인하고,
mechanism, implementation, procedure claim은 full text passage까지 확인한
뒤에만 지지 판정을 내립니다.

단일 DOI 기반 주장에 대해서는 CLI가 abstract 확인을 수행할 수 있습니다.

```bash
ref-verify check-claim <doi> --claim "<specific claim>" --json
```

`check-claim`은 `ACCEPT`일 때만 exit code `0`을 반환합니다. `WARN`,
`PARTIAL`, `UNVERIFIABLE`은 non-zero exit code를 반환합니다. JSON 출력에는
`abstract_source`, `source_attempts`, `error_code`가 포함되어 abstract 부재,
소스 실패, DOI 불일치, 애매한 근거를 구분할 수 있습니다.

초안, 리서치 메모, AI 에이전트 출력처럼 DOI/claim 쌍이 여러 개 있을 때는
`check-file`을 사용합니다.

JSONL:

```bash
ref-verify check-file claims.jsonl
ref-verify check-file claims.jsonl --json
```

CSV:

```bash
ref-verify check-file claims.csv
```

각 행에는 `doi`와 `claim`이 필요합니다. `id`, `source`, `note`는 선택
필드입니다. 기본으로 4행씩 동시에 확인하며(`--workers N`), 출력 순서는 입력
순서를 그대로 따릅니다. CrossRef와 Semantic Scholar 공개 API는 동시 요청을 거절하므로
이 두 곳에는 한 번에 하나씩 보냅니다. 터미널에서 실행하면 stderr에
`Checking claims: N/M` 진행 표시가 나옵니다(`--json`일 때는 나오지 않음). Ctrl-C로
멈출 수 있고, 끝난 조회는 캐시에 남으므로 같은 명령을 다시 실행하면 빠르게 이어집니다. 배치 모드는 기존의 보수적인 `check-claim` 엔진을 그대로
사용합니다. `ACCEPT`는 abstract가 숫자 claim을 명시적으로 지지한다는
뜻입니다. claim에 든 숫자는 단위, 부호, 방향까지 모두 abstract의 한 절이나 문장이
뒷받침해야 합니다. `WARN`, `PARTIAL`, `REJECT`, `UNVERIFIABLE`은 검증된 claim으로
취급하면 안 됩니다.

DOI/claim 쌍이 아니라 참고문헌 목록이 있을 때는 `check-bib`을 사용합니다.
[참고문헌 목록 점검](#참고문헌-목록-점검check-bib)을 보세요.

---

## 오류 코드

현재 `check-claim` error code는 다음과 같습니다.

- `CLAIM_SUPPORTED`: abstract 안에 명시적 근거가 있음
- `CLAIM_NOT_EXPLICIT`: abstract는 있지만 claim을 명시적으로 뒷받침하지 않음
- `CLAIM_AMBIGUOUS`: 숫자나 맥락은 있으나 subject/숫자 연결이 애매함
- `NO_ABSTRACT`: 시도한 DOI-bound source에서 abstract text를 얻지 못함
- `DOI_NOT_FOUND`: CrossRef와 doi.org 어디에도 없는 DOI이거나 선택한 source에서 DOI-bound record를 찾지 못함. JSON에는 `verdict: REJECT`가 함께 담김
- `DOI_NOT_IN_CROSSREF`: CrossRef에는 없지만 doi.org에 다른 등록기관(arXiv·Zenodo의 DataCite, KISTI, JaLC 등)으로 등록된 DOI. `verify-doi`는 서지 정보를 비교하지 않고 `verdict: WARN`, `status: UNVERIFIED`를 반환하고, `check-claim`은 OpenAlex, Semantic Scholar(arXiv DOI는 arXiv 식별자로), PubMed에서 초록을 찾아 있으면 주장을 판정하고 없으면 이 코드와 함께 `status: UNVERIFIABLE`, `verdict: WARN`을 반환합니다. 없는 DOI라는 뜻이 아닙니다
- `PAPER_RETRACTED`: CrossRef에 철회 공지가 있어 초록을 읽기 전에 거절함
- `DOI_MISMATCH`: primary 또는 명시적으로 선택한 DOI-bound record가 요청 DOI와 다름
- `SOURCE_API_ERROR`, `SOURCE_TIMEOUT`, `SOURCE_RATE_LIMITED`, `SOURCE_UNSUPPORTED`: source lookup 실패, timeout, rate limit, 사용 불가

`check-file`은 행마다 같은 코드를 쓰고, 한 행을 확인하지 못하면 `ROW_CHECK_ERROR`를 씁니다.

`check-bib` error code:

- `REFERENCE_RESOLVED`: DOI가 없던 항목을 CrossRef 검색으로 찾았고 `resolved_doi`에 기록함. 연도가 1년 다르거나 제1저자가 다르면 `WARN`
- `REFERENCE_UNMATCHED`: DOI가 없고 일치하는 CrossRef 기록도 찾지 못함(`status: UNVERIFIED`, `verdict: WARN`). 도구가 자동으로 확인하지 못했다는 뜻이지 참고문헌이 틀렸다는 뜻은 아니므로 직접 확인합니다
- `DOI_NOT_IN_CROSSREF`: DOI가 CrossRef가 아닌 다른 등록기관(arXiv·Zenodo의 DataCite, KISTI, JaLC 등)에 등록되어 있어 서지 정보를 비교하지 못함(`status: UNVERIFIED`, `verdict: WARN`). DOI를 직접 열어 확인합니다
- `DOI_NOT_FOUND`: CrossRef와 doi.org 어디에도 없는 DOI(`REJECT`)
- `PAPER_RETRACTED`, `ROW_CHECK_ERROR`: `check-claim`, `check-file`과 같음. 그 밖의 DOI 기반 결과는 `error_code: null`이며 `verdict`, `mismatches`, 그리고 무엇이 다른지 적힌 `reason`(예: `the year differs (reference: 2009; CrossRef: 2010)`)을 봅니다. 일반 텍스트 참고문헌의 DOI가 본문에 없는 다른 논문을 가리키면 `status: MISMATCH`, `verdict: WARN`이고 그 논문 제목이 `reason`에 나옵니다

---

## 저장한 보고서

결과를 공동 저자나 지도교수에게 넘기려면 `check-bib` 또는 `check-file`에
`--report`를 붙입니다. 파일 확장자가 형식을 정합니다.

```bash
ref-verify check-bib references.bib --report report.html
ref-verify check-file claims.jsonl --report report.md
```

HTML 파일은 그 자체로 완결됩니다(인라인 CSS, 스크립트 없음, `https://doi.org/`
링크 외 외부 자원 없음). 맨 위에 합이 전체 개수와 맞는 판정별 개수, 각 판정의 뜻과
할 일을 적은 설명이 있고, 그 아래 통과하지 못한 항목만 모은 "Needs a look" 표와
통과한 항목의 "Passed" 표가 이어집니다. 각 행은 색으로 구분되며(`PASS`/`ACCEPT` 초록,
`WARN` 호박색, `REJECT` 빨강, `UNVERIFIED` 회색) 이유와 근거를 보여 줍니다.
`UNVERIFIED`는 도구가 자동으로 확인하지 못했다는 표시이지 참고문헌이 틀렸다는
판정이 아닙니다. Markdown 파일도 같은 내용입니다. `--report` 경로의 폴더가 없으면
조회를 시작하기 전에 알려 주므로 긴 실행이 헛되지 않습니다. `--json` 출력은 바뀌지 않습니다.

---

## 캐시

CLI는 API 응답을 디스크에 7일 동안 보관하므로, 같은 검사를 다시 돌려도
CrossRef와 abstract 소스에 다시 요청하지 않습니다. HTTP 404가 나온 DOI는
1일만 보관해 새로 등록된 DOI를 곧 다시 확인합니다. 요청 제한(429)과 서버
오류(5xx)는 backoff를 두고 최대 3번 재시도하며(`Retry-After`는 10초까지
따름), 캐시에 남기지 않습니다.

- 위치: `$REF_VERIFY_CACHE_DIR`, 없으면 `$XDG_CACHE_HOME/ref-verify`, 그것도 없으면 `~/.cache/ref-verify`.
- 보관 기간: `REF_VERIFY_CACHE_TTL_DAYS` (기본 `7`).
- 끄기: 모든 명령에서 `--no-cache`, 또는 `REF_VERIFY_NO_CACHE=1`. 비우려면 디렉터리를 지웁니다.
- 내용: 요청 하나당 JSON 파일 하나에 요청 URL, HTTP 상태, 저장 시각, 응답 본문이 들어갑니다. URL에는
  조회한 내용이 그대로 담깁니다. DOI이거나, DOI 없는 참고문헌이면 CrossRef 검색에 보낸 참고문헌 문장이고,
  `REF_VERIFY_MAILTO`를 설정했다면 그 주소도 들어갑니다.

---

## 범위 — 선택적 CLI와 수동 감사의 경계

`ref-verify`는 만능 판정기가 아니라 보수적인 안전장치입니다. 일부러
flag를 더 자주 냅니다. `ACCEPT`는 높은 확신의 통과이고, 그 외 결과는
"자동으로 확인할 수 없으니 사람이 확인해야 한다"는 뜻이지 "인용이
틀렸다"는 뜻은 아닙니다.

**선택적 CLI가 확인하는 것**

- DOI 메타데이터: 제목, 첫 번째 저자 성, 연도를 CrossRef와 비교합니다.
- DOI-bound **abstract**가 특정 숫자 또는 literal claim을 명시적으로
  뒷받침하는지 확인합니다. abstract에 접근할 수 없으면 추측하지 않고
  `UNVERIFIABLE`을 반환합니다.

**선택적 CLI가 확인하지 않는 것** (의도적으로 범위 밖이며 버그가 아닙니다)

- **본문, figure, table, supplementary 값** — abstract-only입니다. 숫자가
  본문에만 있으면 `UNVERIFIABLE`로 남습니다.
- **관계형/정성적 claim** — proportionality, mechanism, "더 강하다/넓다"
  같은 표현은 자동 판정하지 않습니다. value+unit 또는 literal claim 중심입니다.
- **publisher가 abstract를 공개 API에 제공하지 않는 논문** — CrossRef나
  OpenAlex에서 abstract가 없으면 `UNVERIFIABLE`입니다. 이는 claim 판단이
  아니라 접근 가능성 판단입니다.
- **복잡한 통계 지표** — p-value, AUC/AUROC, F1, hazard/odds ratio,
  confidence interval은 CLI가 아니라 수동 skill protocol 범위입니다.
- **논문 품질, novelty, 학계 consensus**, 또는 논문 전체가 넓은 주장을
  뒷받침하는지 여부.

에이전트 스킬의 수동 Full Audit 프로토콜은 mechanism, implementation,
procedure claim에 대해 선택적 CLI보다 더 깊게 확인합니다. 이 경우
full-text passage를 직접 가져와야 하며, 본문에 접근하지 못하면 abstract의
주제 일치만으로 `ACCEPT`하지 않고 `WARN (ABSTRACT-ONLY)`로 남깁니다.

**CLI 주장 판정 읽는 법**

| Verdict | 의미 |
|---|---|
| `ACCEPT` | 가져온 abstract가 claim을 명시적으로 뒷받침함. 높은 확신의 통과. |
| `WARN` / `PARTIAL` | abstract는 읽었지만 정확한 claim을 명시적으로 뒷받침하지 않음. 원문 확인 필요. |
| `UNVERIFIABLE` | 확인할 abstract에 접근하지 못함. claim 자체가 틀렸다는 뜻은 아님. |
| `REJECT` | DOI가 죽었거나, 다른 논문으로 연결되거나, 모순/철회 근거가 있음. |

> 핵심 규칙: 논문 내용에 대한 모든 설명은 claim에 필요한 깊이의
> live-fetched source에서 나와야 합니다. topline claim에는 abstract,
> mechanism, implementation, procedure claim에는 full text가 필요합니다.
> 필요한 source에 접근하지 못하면 그 사실을 밝히고 기억으로 빈칸을
> 채우지 않습니다.

---

## 잡아내는 문제

| 문제 | ref-verify 없이 생기는 일 |
|---|---|
| **잘못된 DOI** | 그럴듯한 DOI가 완전히 다른 논문으로 연결됨 |
| **잘못된 저자** | "Smith et al. (2020)"라고 썼지만 CrossRef에는 단독 저자로 등록됨 |
| **잘못된 연도** | 실제 출판 연도는 2008년인데 초안에는 2011년으로 들어감 |
| **지어낸 내용** | abstract에 없는 결과를 논문이 보여준 것처럼 설명함 |
| **Near-miss citation** | 필요한 숫자는 나오지만 맥락이 다름 |
| **철회 논문** | DOI는 유효하지만 논문이 철회됨 |

---

## 예시

**이미 가진 인용 확인**

```text
사용자: "제출 전에 이 인용 3개를 검증해줘"

Shahinpoor & Kim (2001) 10.1088/0964-1726/10/4/327 - PASS
Bar-Cohen (2004)        10.1117/3.547465            - WARN  (listed as author; CrossRef: editor)
Carpi et al. (2011)     10.1016/B978-0-08-047488-5.00001-0 - REJECT
```

**특정 주장 확인**

```text
사용자: "Pelrine 2000 논문이 DEA가 100% 넘는 strain에 도달한다고 실제로 말해?"

내용: 뒷받침됨
"Actuated strains up to 117% were demonstrated with silicone elastomers,
and up to 215% with acrylic elastomers."
[출처: CrossRef raw JSON, 기억에서 가져온 설명 아님]
```

**Near-miss 인용**

후보 논문 abstract에 "500% strain"이 들어 있어도, 그 숫자가 actuation
result가 아니라 pre-strain condition일 수 있습니다. `ref-verify`는 이런
경우 citation을 받아들이지 않고 `WARN (PARTIAL)`로 표시합니다.

---

## 개발과 릴리스 점검

개발 중 테스트는 다음으로 실행합니다.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

릴리즈 안전성 검사는 Python 패키지를 빌드하고, 메타데이터를 확인하고,
빌드된 wheel을 새 virtualenv에 설치해 본 뒤 배포 경로를 확인합니다. 공개
학술 API를 실제로 호출하는 live check는 수동 GitHub Actions workflow로
분리되어 있어, 일반 CI가 upstream API 일시 장애 때문에 실패하지 않습니다.

참고문헌 점검 벤치마크와 재실행 방법은
[benchmarks/README.md](https://github.com/Moonweave-Research/ref-verify/blob/main/benchmarks/README.md)(영어)에 있습니다.
