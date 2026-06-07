<div align="center">

<img src=".github/assets/ref-verify-mark-512.png" alt="ref-verify mark" width="96">

</div>

# ref-verify

[한국어](https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md) | [English](https://github.com/Moonweave-Research/ref-verify/blob/main/README.md)

**논문이 실제로 말하지 않은 내용을 인용하지 않게 막습니다.**

AI 에이전트에게 논문을 찾아 달라고 하면 DOI는 그럴듯하고, 저자명도 맞아 보이고, 인용 설명도 자연스럽습니다. 하지만 일부는 틀립니다. 보통 그 사실은 리뷰어가 지적할 때까지 드러나지 않습니다.

`ref-verify`는 연구 인용 검증용 에이전트 스킬입니다. Claude Code, Cursor, Codex 같은 스킬 지원 에이전트가 초안에 참고문헌을 넣기 전에 반복 가능한 검증 절차를 따르도록 합니다.

현재 구현은 의도적으로 **스킬/플러그인 수준**입니다. MCP가 아닙니다. 스킬은 DOI 기반 검증이 필요할 때 번들된 Python CLI를 터미널 실행 엔진으로 호출할 수 있습니다. CLI가 증명하지 못하는 부분은 `SKILL.md`의 수동 5-layer 프로토콜로 이어집니다.

현재 CLI가 담당하는 범위:

- CrossRef 기반 DOI 메타데이터 검증: `ref-verify verify-doi`
- CrossRef abstract 기반 claim 검증: `ref-verify check-claim`
- 에이전트가 읽기 쉬운 JSON 출력
- `WARN`, `REJECT`, `UNVERIFIABLE` 결과에 대한 non-zero exit code

아직 스킬 프로토콜이 담당하는 범위:

- Semantic Scholar, Unpaywall, arXiv, PubMed fallback 검증
- DOI landing page 확인
- 두 개 이상의 독립 source로 existence 확인
- retraction 확인

---

## 설치하는 것

```bash
# Node.js에 포함된 npx 필요
npx skills add Moonweave-Research/ref-verify -g
```

**Claude Code, Cursor, Codex** 및 `npx skills` 생태계를 지원하는 에이전트에서 사용할 수 있습니다.

설치 후에는 일반 에이전트 스킬처럼 사용하면 됩니다. 에이전트에게 citation을 verify, audit, find 하라고 자연어로 요청하세요. 이 워크플로우에는 MCP 서버가 필요하지 않습니다. 서버를 시작하거나 MCP를 설정하지 않습니다.

예시 프롬프트:

```text
제출 전에 이 citation들을 검증해줘: [DOI list]
이 논문이 "actuation strain above 100%"라는 claim을 실제로 support해?
claim X를 support하는 논문 3개를 찾고, 각 citation을 검증해줘
이 title/year와 DOI 10.1126/science.287.5454.836이 맞는지 확인해줘
```

### 선택적 실행 엔진

스킬이 agent workflow입니다. Python CLI는 설치된 스킬이 터미널에서 호출할 수 있는 skill-level execution engine이며, 검증하지 못한 부분은 수동 프로토콜로 fallback합니다.

이 워크플로우에는 MCP 서버가 필요하지 않습니다. 현재 CLI 범위는 CrossRef 기반 DOI 메타데이터 검증과 CrossRef abstract 기반 claim 검증입니다. CrossRef가 abstract를 제공하지 않으면 `check-claim`은 `UNVERIFIABLE`을 반환합니다. 이 경우 에이전트 스킬은 Semantic Scholar, Unpaywall, arXiv, PubMed 수동 fallback protocol을 계속 진행할 수 있습니다.

```bash
git clone https://github.com/Moonweave-Research/ref-verify.git
cd ref-verify
python3 -m pip install -e .
```

설치 전 source checkout에서 개발할 때는 `PYTHONPATH`에 source tree를 올려 테스트합니다.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

CLI 사용 가능 여부 확인:

```bash
ref-verify --help
```

설치하지 않은 source checkout에서는 module entrypoint를 사용합니다.

```bash
PYTHONPATH=src python3 -m ref_verify.cli --help
```

집중 검증 예시:

```bash
ref-verify verify-doi 10.1126/science.287.5454.836 \
  --title "High-Speed Electrically Actuated Elastomers with Strain Greater Than 100%" \
  --first-author Pelrine \
  --year 2000 \
  --json

ref-verify check-claim 10.1126/science.287.5454.836 \
  --claim "actuation strain above 100%" \
  --json
```

설치하지 않은 source checkout에서는 같은 검증을 module entrypoint로 실행합니다.

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

## 잡아내는 문제

전체 스킬/수동 workflow는 이런 문제를 잡습니다.

| 문제 | ref-verify 없이 생기는 일 |
|---|---|
| **잘못된 DOI** | 에이전트가 그럴듯한 DOI를 제시하지만 완전히 다른 논문으로 resolve됨 |
| **잘못된 저자** | "Smith et al. (2020)"라고 썼지만 CrossRef에는 Smith 단독 저자로 등록됨 |
| **잘못된 연도** | 실제 출판 연도는 2008년인데 AI가 2011년이라고 확신함 |
| **지어낸 내용** | 에이전트가 "380% strain을 보였다"고 설명하지만 abstract에는 그런 내용이 없음 |
| **Near-miss citation** | 필요한 숫자는 나오지만 다른 맥락임. 예: 결과가 아니라 measurement condition |
| **철회 논문** | DOI는 유효하지만 논문이 retracted 되었고 사용자는 모름 |

---

## 실제 테스트에서 잡은 hallucination

아래 사례는 가정이 아닙니다. 실제 AI 에이전트를 대상으로 이 스킬을 평가하면서 발견한 실패입니다.

**Case 1 - abstract에 없는 content hallucination**

AI 에이전트에게 IPMC actuator strain performance 관련 논문을 찾아 달라고 했습니다. 스킬 없이 실행한 에이전트는 Nemat-Nasser (2002)를 이렇게 설명했습니다.

> *"Develops the first physics-based micromechanical model explicitly predicting strain distribution and tip displacement... provides the quantitative strain-voltage relationship."*

이 설명은 abstract에 없습니다. 실제 CrossRef raw JSON을 가져오면 abstract는 stiffness modeling과 ion effect를 다룹니다. strain distribution prediction이나 strain-voltage relationship은 언급하지 않습니다. 에이전트가 training memory로 빈칸을 채우고 사실처럼 제시한 것입니다.

`ref-verify`를 쓰면 같은 논문은 이렇게 처리됩니다.

```text
CONTENT: WARN Partial
Abstract (CrossRef verbatim): "A systematic experimental evaluation of the mechanical
response of both metal-plated and bare Nafion and Flemion in various cation forms and
various water saturation levels has been performed..."
-> Abstract does not contain a specific strain value. Verify full text before citing
   for a quantitative strain claim.
```

---

**Case 2 - DOI가 완전히 다른 paper로 resolve됨**

reference list에 이런 citation이 있었습니다.

> *Carpi, F. et al. (2011). Dielectric elastomers as electromechanical transducers. Elsevier. DOI: 10.1016/B978-0-08-047488-5.00001-0*

해당 DOI를 fetch하면 edited book의 **Chapter 1**로 resolve됩니다. 저자는 **Ronald Pelrine and Roy Kornbluh**이고 출판 연도는 **2008**입니다. Carpi et al.은 chapter author가 아니라 book editor입니다.

스킬 verdict:

```text
VERDICT: REJECT
DOI resolves to different paper. Year: 2011 (provided) vs 2008 (CrossRef).
Authors: Carpi et al. are editors; chapter authors are Pelrine & Kornbluh.
Corrected book-level DOI: 10.1016/b978-0-08-047488-5.x0001-9
```

---

**Case 3 - 숫자는 맞지만 의미가 틀림**

">100% actuation strain in dielectric elastomers"를 support하는 논문을 찾을 때, abstract에 "500% strain"이 들어간 후보가 나왔습니다. 겉보기에는 강한 근거처럼 보입니다.

하지만 abstract를 읽으면 500%는 electric breakdown field를 측정한 mechanical **pre-strain level**입니다. actuation output이 아닙니다. 이 논문을 "500% actuation strain" 근거로 쓰면 틀립니다.

```text
CONTENT: WARN Partial
Abstract contains "500% strain" but this refers to the pre-strain condition
at which breakdown field (218 MV/m) was measured - not an actuation strain output.
Abstract does not explicitly report an actuation strain result.
VERDICT: WARN - does not meet the ACCEPT threshold for this specific claim.
```

---

## 사용 예시

**설명으로 논문을 찾을 때 - 사용자에게 도달하기 전에 검증**

```text
User: "find papers showing cancer cells are stiffer than healthy cells"

ref-verify Full Audit:

REFERENCE AUDIT
────────────────────────────────────────────────────────
Paper:   Biomechanical properties of cancer cells
DOI:     10.1088/0957-4484/18/18/185101 - Resolves (paywalled)
Authors: Bhanu Ponugoti, et al.  -> MISMATCH: CrossRef returns Cross, S.E. et al.
Year:    2007 - Consistent

VERDICT: WARN - author list does not match CrossRef record. Verify before citing.
────────────────────────────────────────────────────────
```

**이미 가진 citation 검증 - reference list 안의 잘못된 DOI 탐지**

```text
User: "verify these 3 citations before I submit"

Shahinpoor & Kim (2001) 10.1088/0964-1726/10/4/327 - PASS
Bar-Cohen (2004)        10.1117/3.547465            - WARN  (listed as author; CrossRef: editor)
Carpi et al. (2011)     10.1016/B978-0-08-047488-5.00001-0 - REJECT (DOI resolves to different paper,
                                                               year is 2008 not 2011, different authors)
```

**특정 claim 검증 - abstract가 정말 그 내용을 말하는지 확인**

```text
User: "does the Pelrine 2000 paper actually say DEAs reach over 100% strain?"

CONTENT: Supported
"Actuated strains up to 117% were demonstrated with silicone elastomers,
and up to 215% with acrylic elastomers."
[Source: CrossRef raw JSON, fetched 2026-06-01 - not recalled from memory]
```

---

## 언제 트리거되는가

자연어로 말하면 됩니다. `ref-verify`는 citation task에서 자동으로 활성화됩니다.

```text
"find 3 papers supporting the claim that X"
"verify these citations before I submit: [DOI list]"
"check doi 10.1002/adma.202108361 - I think I copied it wrong"
"is that actually what the paper says?"
"audit all my references before submission"
"add a citation for the paper where [author] showed [finding]"
```

일반 주제 설명, 문장 다듬기, APA formatting, citation style 질문에는 조용히 있습니다.

---

## 두 가지 모드 - 자동 선택

**Quick Screen** - DOI를 이미 가지고 있을 때 사용합니다. CrossRef를 조회하고 title + author match를 확인하며 DOI resolve 여부를 봅니다. paper당 몇 초 수준입니다.

CrossRef metadata portion에는 다음 명령을 사용합니다.

```bash
ref-verify verify-doi <doi> --title "<title>" --first-author <last-name> --year <year> --json
```

`verify-doi`는 `PASS`일 때만 exit code `0`을 반환합니다. `WARN`과 `REJECT`는 non-zero exit code를 반환하므로, 누락되었거나 mismatched comparison metadata가 automation gate를 조용히 통과할 수 없습니다.

**Full Audit** - 처음부터 논문을 찾거나 최종 제출 전 citation sweep을 할 때 사용합니다. CrossRef -> Semantic Scholar -> Unpaywall -> arXiv -> PubMed 순서로 abstract를 live fetch합니다. abstract가 실제로 특정 claim을 포함하는지 확인합니다. 접근 가능한 abstract가 없으면 `UNVERIFIABLE`로 명시하고 추측하지 않습니다.

단일 DOI-backed claim에는 다음 명령을 사용합니다.

```bash
ref-verify check-claim <doi> --claim "<specific claim>" --json
```

이 명령은 보수적으로 동작합니다. fetch된 CrossRef abstract가 support하는 것만 accept하고, abstract가 없으면 `UNVERIFIABLE`로 표시합니다.

`check-claim`은 `ACCEPT`일 때만 exit code `0`을 반환합니다. `WARN`, `PARTIAL`, `UNVERIFIABLE`은 automation gate용 non-zero exit code를 반환합니다.

CLI는 아직 전체 수동 Quick Screen을 대체하지 않습니다. 필요한 경우 DOI landing-page resolution, second-source confirmation, retraction check는 계속 스킬 프로토콜을 따라야 합니다.

> **절대 완화하지 않는 규칙:** paper content에 대한 모든 statement는 live-fetched abstract에서 나와야 하며, 가능하면 그대로 quote해야 합니다. 모든 fallback 후에도 abstract에 접근할 수 없으면 그렇게 말합니다. training data로 빈칸을 채우지 않습니다.

---

## Near-miss detection

존재 확인만으로는 부족합니다. 스킬은 abstract가 인용하려는 **specific claim**을 실제로 support하는지 확인합니다.

논문이 필요한 숫자와 똑같아 보이는 값을 언급하더라도, 그 값이 다른 physical quantity, measurement condition, baseline일 수 있습니다. claim checking이 없으면 이런 citation은 통과합니다. `ref-verify`를 쓰면 `WARN (PARTIAL)`과 설명으로 flag됩니다.

---

## 5-layer verification

1. **Existence** - CrossRef + Semantic Scholar처럼 두 개의 독립 source가 필요합니다. single-source 결과는 flag됩니다.
2. **Metadata** - title, all authors, year, journal을 cross-check합니다. mismatch는 조용히 선택하지 않고 명시합니다.
3. **Content traceability** - priority order에 따라 5개 source에서 abstract를 fetch합니다. output에는 verbatim quote가 포함됩니다. 접근할 수 없으면 `UNVERIFIABLE`입니다.
4. **DOI resolution** - `doi.org` fetch로 landing page가 expected paper와 맞는지 확인합니다.
5. **Retraction** - web search와 DOI landing page banner로 retraction을 확인합니다.

---

## 관련 프로젝트

- [anneal-skill](https://github.com/Moonweave-Systems/anneal-skill) - AI agent용 measure-first decision discipline
- [decide-skill](https://github.com/Moonweave-Systems/decide-skill) - 비전문가 domain을 위한 decision automation
