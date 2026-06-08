<div align="center">

<img src="https://raw.githubusercontent.com/Moonweave-Research/ref-verify/main/.github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

</div>

# ref-verify

[한국어](https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md) | [English](https://github.com/Moonweave-Research/ref-verify/blob/main/README.md)

**논문에 없는 내용을 인용하지 않도록 막습니다.**

`ref-verify`는 연구 인용 검증용 에이전트 스킬입니다. Claude Code,
Cursor, Codex 같은 스킬 지원 에이전트가 초안에 참고문헌을 넣기 전에
반복 가능한 검증 절차를 따르도록 합니다.

논문 찾기, DOI 확인, 특정 주장을 논문이 실제로 뒷받침하는지 확인,
제출 전 참고문헌 점검에 사용할 수 있습니다. 서버를 시작하거나 MCP를 설정할 필요가 없습니다.

---

## 스킬 설치

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

에이전트가 CLI를 호출할 때 따라야 할 명시적 규칙은
[AGENT_USAGE.md](https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md)를 참고하세요.

---

## 사용 방법

자연스럽게 요청하면 됩니다.

```text
제출 전에 이 인용들을 검증해줘: [DOI list]
이 논문이 "actuation strain above 100%"라는 주장을 실제로 뒷받침해?
claim X를 뒷받침하는 논문 3개를 찾고, 각 인용을 검증해줘
이 title/year와 DOI 10.1126/science.287.5454.836이 맞는지 확인해줘
제출 전에 참고문헌 전체를 점검해줘
```

일반 주제 설명, 문장 다듬기, APA/IEEE 형식 정리, 인용 스타일 질문에는
조용히 있습니다.

---

## 선택적 CLI 엔진

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
- 에이전트가 읽기 쉬운 JSON 출력
- `WARN`, `REJECT`, `UNVERIFIABLE` 결과에 대한 non-zero exit code

`p-value`, AUC/AUROC, F1 score, hazard ratio, odds ratio, confidence interval
같은 통계 지표는 아직 수동 스킬 프로토콜을 따릅니다. DOI landing page 확인은 스킬 프로토콜을 따릅니다. Unpaywall, arXiv, 두 개 이상의 독립 출처로 존재 확인,
철회 여부 확인도 `SKILL.md`에 있는 스킬 프로토콜이 담당합니다.

CLI에는 third-party Python runtime dependency가 없지만, offline verifier는
아닙니다. 실제 검증에는 CrossRef, OpenAlex, Semantic Scholar, PubMed 같은 공개 학술
API로 outbound HTTPS 요청을 보낼 수 있어야 합니다.

로컬 체크아웃에서 CLI를 설치합니다.

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

개발 중 테스트는 다음으로 실행합니다.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

릴리즈 안전성 검사는 Python 패키지를 빌드하고, 메타데이터를 확인하고,
빌드된 wheel을 새 virtualenv에 설치해 본 뒤 배포 경로를 확인합니다. 공개
학술 API를 실제로 호출하는 live check는 수동 GitHub Actions workflow로
분리되어 있어, 일반 CI가 upstream API 일시 장애 때문에 실패하지 않습니다.

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
통해 abstract를 가져오고, 논문이 인용하려는 특정 주장을 뒷받침하는지
확인합니다.

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
필드입니다. 배치 모드는 기존의 보수적인 `check-claim` 엔진을 그대로
사용합니다. `ACCEPT`는 abstract가 숫자 claim을 명시적으로 지지한다는
뜻입니다. `WARN`, `PARTIAL`, `REJECT`, `UNVERIFIABLE`은 검증된 claim으로
취급하면 안 됩니다.

현재 `check-claim` error code는 다음과 같습니다.

- `CLAIM_SUPPORTED`: abstract 안에 명시적 근거가 있음
- `CLAIM_NOT_EXPLICIT`: abstract는 있지만 claim을 명시적으로 뒷받침하지 않음
- `CLAIM_AMBIGUOUS`: 숫자나 맥락은 있으나 subject/숫자 연결이 애매함
- `NO_ABSTRACT`: 시도한 DOI-bound source에서 abstract text를 얻지 못함
- `DOI_NOT_FOUND`: 선택한 source에서 DOI-bound record를 찾지 못함
- `DOI_MISMATCH`: primary 또는 명시적으로 선택한 DOI-bound record가 요청 DOI와 다름
- `SOURCE_API_ERROR`, `SOURCE_TIMEOUT`, `SOURCE_RATE_LIMITED`, `SOURCE_UNSUPPORTED`: source lookup 실패, timeout, rate limit, 사용 불가

> 핵심 규칙: 논문 내용에 대한 모든 설명은 live-fetched abstract에서
> 나와야 합니다. fallback 확인 후에도 abstract에 접근할 수 없으면
> `UNVERIFIABLE`이라고 말합니다. 기억으로 빈칸을 채우지 않습니다.

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

## 관련 프로젝트

- [anneal-skill](https://github.com/Moonweave-Systems/anneal-skill) - AI agent용 measure-first decision discipline
- [decide-skill](https://github.com/Moonweave-Systems/decide-skill) - 비전문가 domain을 위한 decision automation
