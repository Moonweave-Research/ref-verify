"""Write truth.json: what is wrong (and right) in each e2e manuscript.

Each item names a reference or a cited claim, the planted error type (or OK), how to
recognise it in an agent's answer (`match`: identifiers; `value`: the wrong value for a
claim), and the verified facts. Run once; truth.json is committed.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

ERROR_TYPES = (
    "FAB_DOI",
    "FAB_NODOI",
    "DOI_SWAP",
    "RETRACTED",
    "WRONG_YEAR",
    "WRONG_AUTHOR",
    "TITLELESS_WRONG_VOLPAGE",
    "CLAIM_NUMBER",
    "CLAIM_UNIT",
    "CLAIM_DIRECTION",
)


def ok(ref: str, match: list[str], doi: str | None, note: str = "") -> dict:
    return {"ref": ref, "type": "OK", "match": match, "truth_doi": doi, "note": note}


def unindexed(ref: str, match: list[str], source: str) -> dict:
    return {"ref": ref, "type": "UNINDEXED_OK", "match": match, "truth_doi": None, "source": source}


def error(ref: str, kind: str, match: list[str], problem: str, fix: str, doi: str | None = None, **extra) -> dict:
    assert kind in ERROR_TYPES, kind
    return {"ref": ref, "type": kind, "match": match, "truth_doi": doi, "problem": problem, "fix": fix, **extra}


def claim(ref: str, kind: str, match: list[str], value: list[str], text: str, abstract: str, doi: str) -> dict:
    assert kind in ("CLAIM_NUMBER", "CLAIM_UNIT", "CLAIM_DIRECTION", "CLAIM_OK")
    return {
        "ref": ref,
        "type": kind,
        "match": match,
        "value": value,
        "claim_text": text,
        "abstract_says": abstract,
        "truth_doi": doi,
    }


MANUSCRIPTS = {
    "m1_dea_en": {
        "path": "manuscripts/m1_dea_en.md",
        "language": "en",
        "format": "markdown (APA, author-date)",
        "domain": "materials / polymers",
        "items": [
            ok("Acome et al., 2018", ["Acome"], "10.1126/science.aao6139"),
            ok("Brochu & Pei, 2010", ["Brochu & Pei", "Brochu and Pei", "Brochu, P., & Pei"], "10.1002/marc.200900425"),
            ok("Carpi et al., 2010", ["Carpi"], "10.1126/science.1194773"),
            ok("Duduta et al., 2019", ["Duduta"], "10.1073/pnas.1815053116"),
            ok("Ha et al., 2006", ["Ha et al", "Ha, S. M."], "10.1002/adma.200502437"),
            ok("Keplinger et al., 2013", ["Keplinger"], "10.1126/science.1240228"),
            error(
                "Madsen & Skov, 2017",
                "DOI_SWAP",
                ["Madsen"],
                "DOI 10.1002/marc.201500576 is 'The Current State of Silicone-Based Dielectric Elastomer "
                "Transducers' (Madsen, Daugaard, Hvilsted, Skov, 2016); no paper with the cited title exists.",
                "Cite the 2016 review with its real title, or remove the reference.",
                doi="10.1002/marc.201500576",
            ),
            error(
                "Pei & Brochu, 2014",
                "FAB_DOI",
                ["Pei & Brochu", "Pei and Brochu", "Pei, Q., & Brochu", "adma.201305412"],
                "DOI 10.1002/adma.201305412 does not exist (CrossRef 404, doi.org 'DOI does not exist'); "
                "no such paper.",
                "Remove the reference and the claims that rest on it.",
            ),
            ok("Pelrine et al., 2000", ["Pelrine"], "10.1126/science.287.5454.836"),
            ok("Poulin et al., 2015", ["Poulin"], "10.1063/1.4937735"),
            error(
                "Romasanta et al., 2013",
                "WRONG_YEAR",
                ["Romasanta"],
                "Published 2015 (Prog. Polym. Sci. 51), not 2013.",
                "Change the year to 2015.",
                doi="10.1016/j.progpolymsci.2015.08.002",
                cited_year=2013,
                true_year=2015,
            ),
            ok("Suo, 2010", ["Suo"], "10.1016/S0894-9166(11)60004-9"),
            claim(
                "Pelrine et al., 2000",
                "CLAIM_NUMBER",
                ["Pelrine"],
                ["380"],
                "actuated strains of up to 380% with acrylic elastomers",
                "Actuated strains up to 117% were demonstrated with silicone elastomers, and up to 215% with "
                "acrylic elastomers",
                "10.1126/science.287.5454.836",
            ),
            claim(
                "Poulin et al., 2015",
                "CLAIM_DIRECTION",
                ["Poulin"],
                ["above 300"],
                "keeps the operation voltage above 300 V",
                "reducing the operation voltage below 300 V while keeping good actuation strain",
                "10.1063/1.4937735",
            ),
            claim(
                "Ha et al., 2006",
                "CLAIM_OK",
                ["Ha et al", "233"],
                ["233"],
                "233% area strain at 300 MV/m without any external prestrain",
                "Strains of up to 233% in terms of area expansion have been obtained at an electrical field of "
                "300 MV m-1",
                "10.1002/adma.200502437",
            ),
        ],
    },
    "m2_vaccine_en": {
        "path": "manuscripts/m2_vaccine_en.md",
        "language": "en",
        "format": "markdown (Vancouver, numbered)",
        "domain": "biomedicine",
        "items": [
            ok("[1]", ["[1]", "Polack"], "10.1056/NEJMoa2034577"),
            error(
                "[2]",
                "WRONG_AUTHOR",
                ["[2]", "El Sahly", "Baden"],
                "First author is Baden LR; El Sahly HM is second.",
                "List the authors as Baden LR, El Sahly HM, Essink B, et al.",
                doi="10.1056/NEJMoa2035389",
            ),
            ok("[3]", ["[3]", "Zhou"], "10.1038/s41586-020-2012-7"),
            ok("[4]", ["[4]", "Huang"], "10.1016/S0140-6736(20)30183-5"),
            error(
                "[5]",
                "RETRACTED",
                ["[5]", "Mehra"],
                "Retracted by The Lancet in June 2020 (CrossRef updated-by: retraction).",
                "Remove it, or cite it only as a retracted study.",
                doi="10.1016/S0140-6736(20)31180-6",
            ),
            ok("[6]", ["[6]", "Livak"], "10.1006/meth.2001.1262"),
            ok("[7]", ["[7]", "Jumper"], "10.1038/s41586-021-03819-2"),
            ok("[8]", ["[8]", "Jinek"], "10.1126/science.1225829"),
            error(
                "[9]",
                "FAB_NODOI",
                ["[9]", "Chen L", "Okafor", "neurofilament"],
                "No such paper (no CrossRef record with this title; Lancet Neurol 22(5) has no such article).",
                "Remove the reference.",
            ),
            ok("[10]", ["[10]", "Cong"], "10.1126/science.1231143"),
            ok("[11]", ["[11]", "Gulshan"], "10.1001/jama.2016.17216"),
            claim(
                "[1]",
                "CLAIM_NUMBER",
                ["[1]", "Polack", "BNT162b2"],
                ["85%", "85 %"],
                "BNT162b2 ... was 85% effective in preventing Covid-19",
                "BNT162b2 was 95% effective in preventing Covid-19",
                "10.1056/NEJMoa2034577",
            ),
            claim(
                "[1]",
                "CLAIM_UNIT",
                ["[1]", "Polack", "BNT162b2"],
                ["30 mg"],
                "two doses of 30 mg each",
                "BNT162b2 vaccine candidate (30 μg per dose)",
                "10.1056/NEJMoa2034577",
            ),
            claim(
                "[2]",
                "CLAIM_OK",
                ["94.1"],
                ["94.1"],
                "mRNA-1273 showed 94.1% efficacy",
                "vaccine efficacy was 94.1%",
                "10.1056/NEJMoa2035389",
            ),
            claim(
                "[3]",
                "CLAIM_OK",
                ["96%"],
                ["96%"],
                "shares 96% whole-genome identity with a bat coronavirus",
                "2019-nCoV is 96% identical at the whole-genome level to a bat coronavirus",
                "10.1038/s41586-020-2012-7",
            ),
        ],
    },
    "m3_ml_en": {
        "path": "manuscripts/m3_ml_en.md",
        "language": "en",
        "format": "markdown (IEEE, numbered)",
        "domain": "machine learning",
        "items": [
            ok("[1]", ["[1]", "He et al", "residual"], "10.1109/CVPR.2016.90"),
            ok("[2]", ["[2]", "LeCun"], "10.1038/nature14539"),
            ok("[3]", ["[3]", "Silver"], "10.1038/nature16961"),
            ok("[4]", ["[4]", "Krizhevsky"], "10.1145/3065386"),
            ok("[5]", ["[5]", "Hochreiter"], "10.1162/neco.1997.9.8.1735"),
            ok("[6]", ["[6]", "Devlin", "BERT"], "10.18653/v1/N19-1423"),
            unindexed("[7]", ["[7]", "Vaswani"], "https://papers.nips.cc/paper/7181-attention-is-all-you-need"),
            unindexed("[8]", ["[8]", "Srivastava", "Dropout"], "https://jmlr.org/papers/v15/srivastava14a.html"),
            error(
                "[9]",
                "WRONG_YEAR",
                ["[9]", "Mnih"],
                "Nature 518, 529-533 was published in 2015, not 2013 (the 2013 work is the arXiv workshop paper "
                "'Playing Atari with deep reinforcement learning').",
                "Change the year to 2015.",
                doi="10.1038/nature14236",
                cited_year=2013,
                true_year=2015,
            ),
            error(
                "[10]",
                "FAB_DOI",
                ["[10]", "Zhang", "mixture-of-experts", "s42256-021-00381-9"],
                "DOI 10.1038/s42256-021-00381-9 does not exist; no such paper.",
                "Remove the reference and the sentence it supports.",
            ),
            error(
                "[11]",
                "DOI_SWAP",
                ["[11]", "Kingma", "variational"],
                "The DOI 10.1162/neco.1997.9.8.1735 is Hochreiter & Schmidhuber's LSTM paper; the VAE paper "
                "is an ICLR 2014 / arXiv:1312.6114 work without that DOI.",
                "Replace the DOI with arXiv:1312.6114 (or doi:10.48550/arXiv.1312.6114).",
                doi="10.1162/neco.1997.9.8.1735",
            ),
            ok("[12]", ["[12]", "Ronneberger", "U-Net"], "10.1007/978-3-319-24574-4_28"),
            claim(
                "[4]",
                "CLAIM_NUMBER",
                ["[4]", "Krizhevsky", "ImageNet"],
                ["27.5"],
                "reached a top-1 error rate of 27.5%",
                "we achieved top-1 and top-5 error rates of 37.5% and 17.0%",
                "10.1145/3065386",
            ),
            claim(
                "[4]",
                "CLAIM_OK",
                ["650,000", "60 million"],
                ["650,000", "60 million"],
                "650,000 neurons and 60 million parameters",
                "The neural network, which has 60 million parameters and 650,000 neurons",
                "10.1145/3065386",
            ),
        ],
    },
    "m4_physics_en": {
        "path": "manuscripts/m4_physics_en.md",
        "language": "en",
        "format": "markdown (physics style, no article titles)",
        "domain": "physics",
        "items": [
            ok("[1]", ["[1]", "Bardeen", "BCS"], "10.1103/physrev.108.1175"),
            ok("[2]", ["[2]", "Einstein", "EPR"], "10.1103/physrev.47.777"),
            ok("[3]", ["[3]", "Riess"], "10.1086/300499"),
            ok("[4]", ["[4]", "Perlmutter"], "10.1086/307221"),
            ok("[5]", ["[5]", "Science 306"], "10.1126/science.1102896"),
            ok("[6]", ["[6]", "Abbott", "LIGO"], "10.1103/PhysRevLett.116.061102"),
            ok("[7]", ["[7]", "Hasan"], "10.1103/revmodphys.82.3045"),
            error(
                "[8]",
                "TITLELESS_WRONG_VOLPAGE",
                ["[8]", "Nature 438", "438, 297"],
                "Novoselov et al., Nature 438 starts on page 197 ('Two-dimensional gas of massless Dirac fermions "
                "in graphene'), not 297.",
                "Change the page to 197 (doi:10.1038/nature04233).",
                doi="10.1038/nature04233",
            ),
            error(
                "[9]",
                "TITLELESS_WRONG_VOLPAGE",
                ["[9]", "Geim", "Nat. Mater. 7", "rise of graphene"],
                "'The rise of graphene' is Nat. Mater. 6, 183 (2007), not volume 7.",
                "Change the volume to 6 (doi:10.1038/nmat1849).",
                doi="10.1038/nmat1849",
            ),
            error(
                "[10]",
                "RETRACTED",
                ["[10]", "Snider", "carbonaceous", "Nature 586"],
                "Retracted by Nature in 2022 (CrossRef updated-by: retraction).",
                "Remove it, or cite it only as a retracted claim.",
                doi="10.1038/s41586-020-2801-z",
            ),
            error(
                "[11]",
                "FAB_NODOI",
                ["[11]", "Okafor", "CrI3"],
                "No such paper (no CrossRef record with this title).",
                "Remove the reference and the claim.",
            ),
            claim(
                "[6]",
                "CLAIM_UNIT",
                ["[6]", "Abbott", "LIGO", "GW150914"],
                ["410 kpc", "kpc"],
                "observed at a luminosity distance of 410 kpc",
                "The source lies at a luminosity distance of 410 (+160/-180) Mpc",
                "10.1103/PhysRevLett.116.061102",
            ),
            claim(
                "[6]",
                "CLAIM_DIRECTION",
                ["[6]", "Abbott", "LIGO", "GW150914"],
                ["greater than 1 event", "false alarm"],
                "with a false alarm rate greater than 1 event per 203 000 years",
                "a false alarm rate estimated to be less than 1 event per 203 000 years",
                "10.1103/PhysRevLett.116.061102",
            ),
            claim(
                "[5]",
                "CLAIM_OK",
                ["10,000", "10 000"],
                ["10,000"],
                "room-temperature mobilities of about 10,000 cm²/V·s",
                "room-temperature mobilities of ~10,000 square centimeters per volt-second",
                "10.1126/science.1102896",
            ),
        ],
    },
    "m5_dea_latex": {
        "path": "manuscripts/m5_dea_latex/main.tex",
        "bib": "manuscripts/m5_dea_latex/references.bib",
        "language": "en",
        "format": "LaTeX + BibTeX",
        "domain": "materials / polymers",
        "items": [
            ok("pelrine1998", ["pelrine1998"], "10.1016/S0924-4247(97)01657-9"),
            ok("kofod2003", ["kofod2003", "Kofod"], "10.1177/104538903039260"),
            ok("ha2006", ["ha2006"], "10.1002/adma.200502437"),
            ok("plante2006", ["plante2006", "Plante"], "10.1016/j.ijsolstr.2006.03.026"),
            ok("wissler2005", ["wissler2005", "Wissler"], "10.1088/0964-1726/14/6/032"),
            ok("jordi2011", ["jordi2011", "Jordi"], "10.1088/0964-1726/20/7/075003"),
            error(
                "shahinpoor2001",
                "WRONG_AUTHOR",
                ["shahinpoor2001"],
                "First author is Shahinpoor, M.; the entry lists Kim, K. J. first.",
                "Swap the author order to Shahinpoor, Mohsen and Kim, Kwang J.",
                doi="10.1088/0964-1726/10/4/327",
            ),
            ok("opris2018", ["opris2018"], "10.1002/adma.201703678"),
            error(
                "hines2017",
                "DOI_SWAP",
                ["hines2017"],
                "The DOI 10.1002/adma.201703678 is Opris 2018 (also in this .bib); Hines et al. 2017 is "
                "10.1002/adma.201603483.",
                "Change the DOI to 10.1002/adma.201603483.",
                doi="10.1002/adma.201703678",
                correct_doi="10.1002/adma.201603483",
            ),
            ok("poulin2015", ["poulin2015", "Poulin"], "10.1063/1.4937735"),
            error(
                "kim2020selfhealing",
                "FAB_DOI",
                ["kim2020selfhealing", "liquid-metal", "adfm.202001234"],
                "DOI 10.1002/adfm.202001234 does not exist; no such paper.",
                "Remove the entry and the sentence it supports.",
            ),
            error(
                "dasenbrock2023",
                "RETRACTED",
                ["dasenbrock2023", "Dasenbrock", "lutetium"],
                "Retracted by Nature in November 2023 (CrossRef updated-by: retraction).",
                "Remove it.",
                doi="10.1038/s41586-023-05742-0",
            ),
            claim(
                "kofod2003",
                "CLAIM_UNIT",
                ["kofod2003", "Kofod"],
                ["20 kV", "kilo", "kV/m", "kV m"],
                "breakdown field rises from 20 kV/m in the unstrained state",
                "In the unstrained state the breakdown field is 20 MV/m",
                "10.1177/104538903039260",
            ),
            claim(
                "ha2006",
                "CLAIM_OK",
                ["ha2006", "233"],
                ["233"],
                "233% area strain at 300 MV/m",
                "Strains of up to 233% ... at an electrical field of 300 MV m-1",
                "10.1002/adma.200502437",
            ),
        ],
    },
    "m6_biomed_latex": {
        "path": "manuscripts/m6_biomed_latex/main.tex",
        "bib": "manuscripts/m6_biomed_latex/references.bib",
        "language": "en",
        "format": "LaTeX + BibTeX",
        "domain": "biomedicine",
        "items": [
            ok("jinek2012", ["jinek2012"], "10.1126/science.1225829"),
            ok("cong2013", ["cong2013"], "10.1126/science.1231143"),
            error(
                "doudna2016",
                "WRONG_YEAR",
                ["doudna2016", "Doudna"],
                "Science 346, 1258096 was published in 2014, not 2016.",
                "Change year to 2014 (and the key if you like).",
                doi="10.1126/science.1258096",
                cited_year=2016,
                true_year=2014,
            ),
            ok("livak2001", ["livak2001", "Livak"], "10.1006/meth.2001.1262"),
            ok("esteva2017", ["esteva2017", "Esteva"], "10.1038/nature21056"),
            ok("gulshan2016", ["gulshan2016", "Gulshan"], "10.1001/jama.2016.17216"),
            ok("ronneberger2015", ["ronneberger2015"], "10.1007/978-3-319-24574-4_28"),
            ok("jumper2021", ["jumper2021"], "10.1038/s41586-021-03819-2"),
            error(
                "okonkwo2022",
                "FAB_NODOI",
                ["okonkwo2022", "Okonkwo", "sepsis"],
                "No such paper (no CrossRef record with this title).",
                "Remove the entry and the sentence it supports.",
            ),
            ok("zhou2020", ["zhou2020"], "10.1038/s41586-020-2012-7"),
            ok("polack2020", ["polack2020", "Polack"], "10.1056/NEJMoa2034577"),
            error(
                "wakefield1998",
                "RETRACTED",
                ["wakefield1998", "Wakefield"],
                "Retracted by The Lancet in 2010 (CrossRef updated-by: retraction).",
                "Remove it; it cannot support the sentence.",
                doi="10.1016/S0140-6736(97)11096-0",
            ),
            claim(
                "gulshan2016",
                "CLAIM_DIRECTION",
                ["gulshan2016", "Gulshan"],
                ["below 85", "85%", "85\\%"],
                "the operating point selected for high sensitivity still gave a sensitivity below 85% in EyePACS-1",
                "Using a second operating point with high sensitivity ... for EyePACS-1 the sensitivity was 97.5%",
                "10.1001/jama.2016.17216",
            ),
            claim(
                "zhou2020",
                "CLAIM_NUMBER",
                ["zhou2020", "Zhou"],
                ["99%", "99\\%"],
                "SARS-CoV-2 is 99% identical at the whole-genome level to a bat coronavirus",
                "2019-nCoV is 96% identical at the whole-genome level to a bat coronavirus",
                "10.1038/s41586-020-2012-7",
            ),
            claim(
                "polack2020",
                "CLAIM_OK",
                ["95%", "95\\%"],
                ["95"],
                "mRNA vaccines reached 95% efficacy",
                "BNT162b2 was 95% effective",
                "10.1056/NEJMoa2034577",
            ),
        ],
    },
    "m7_polymer_ko": {
        "path": "manuscripts/m7_polymer_ko.md",
        "language": "ko",
        "format": "markdown (Korean, numbered)",
        "domain": "materials / polymers",
        "items": [
            ok("[1]", ["[1]", "윤혜리"], "10.7317/pk.2012.36.4.455"),
            error(
                "[2]",
                "WRONG_YEAR",
                ["[2]", "안다훈"],
                "폴리머 45(6) 948-954는 2021년 발행(DOI 10.7317/pk.2021.45.6.948), 2019년이 아님.",
                "연도를 2021로 고친다.",
                doi="10.7317/pk.2021.45.6.948",
                cited_year=2019,
                true_year=2021,
            ),
            ok("[3]", ["[3]", "박재우"], "10.7317/pk.2023.47.6.750"),
            unindexed("[4]", ["[4]", "강동휘"], "https://dl.nanet.go.kr/detail/KDMT12026000014012"),
            unindexed(
                "[5]",
                ["[5]", "정진석"],
                "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci (Polymer Korea 31(4) 308-314)",
            ),
            ok("[6]", ["[6]", "Brochu"], "10.1002/marc.200900425", note="title-less physics style"),
            ok("[7]", ["[7]", "Carpi"], "10.1126/science.1194773"),
            ok("[8]", ["[8]", "Poulin"], "10.1063/1.4937735"),
            error(
                "[9]",
                "FAB_DOI",
                ["[9]", "이민수", "이온성 액체", "pk.2022.46.2.215"],
                "DOI 10.7317/pk.2022.46.2.215는 존재하지 않음(CrossRef 404, doi.org 'DOI does not exist').",
                "참고문헌과 해당 문장을 삭제한다.",
            ),
            error(
                "[10]",
                "DOI_SWAP",
                ["[10]", "최수아", "형상기억"],
                "DOI 10.7317/pk.2021.45.6.897은 김호연·이종휘의 '온도감응성 하이드로젤 기반 증발 결정화 시스템'이며, "
                "인용된 제목·저자의 논문은 없음.",
                "올바른 문헌으로 바꾸거나 삭제한다.",
                doi="10.7317/pk.2021.45.6.897",
            ),
            ok("[11]", ["[11]", "Kofod"], "10.1177/104538903039260"),
            claim(
                "[8]",
                "CLAIM_UNIT",
                ["[8]", "Poulin"],
                ["3 mm"],
                "3 mm 두께의 막에서 245 V만으로 7.5%의 측면 변형",
                "We achieve a lateral actuation strain of 7.5% at only 245 V on a 3 μm thick pad-printed membrane",
                "10.1063/1.4937735",
            ),
            claim(
                "[11]",
                "CLAIM_OK",
                ["20 MV/m"],
                ["20 MV/m"],
                "변형되지 않은 상태의 절연파괴 전계는 20 MV/m",
                "In the unstrained state the breakdown field is 20 MV/m",
                "10.1177/104538903039260",
            ),
        ],
    },
    "m8_ml_ko": {
        "path": "manuscripts/m8_ml_ko.md",
        "language": "ko",
        "format": "markdown (Korean, numbered, APA list)",
        "domain": "machine learning / physics",
        "items": [
            ok("[1]", ["[1]", "He, K."], "10.1109/CVPR.2016.90"),
            error(
                "[2]",
                "WRONG_AUTHOR",
                ["[2]", "Hinton", "LeCun"],
                "First author is LeCun, Y. (LeCun, Bengio, Hinton), not Hinton.",
                "Write LeCun, Y., Bengio, Y., & Hinton, G. (2015).",
                doi="10.1038/nature14539",
            ),
            ok("[3]", ["[3]", "Silver"], "10.1038/nature16961"),
            ok("[4]", ["[4]", "Krizhevsky"], "10.1145/3065386"),
            ok("[5]", ["[5]", "Hochreiter"], "10.1162/neco.1997.9.8.1735"),
            ok("[6]", ["[6]", "Mnih"], "10.1038/nature14236"),
            unindexed("[7]", ["[7]", "Kingma", "Adam"], "https://arxiv.org/abs/1412.6980"),
            error(
                "[8]",
                "FAB_DOI",
                ["[8]", "김지훈", "JOK.2022.49.3.211"],
                "DOI 10.5626/JOK.2022.49.3.211은 존재하지 않음.",
                "참고문헌과 해당 문장을 삭제한다.",
            ),
            error(
                "[9]",
                "FAB_NODOI",
                ["[9]", "Park, S.", "Quantum-inspired"],
                "No such paper (no CrossRef record with this title).",
                "Remove the reference.",
            ),
            error(
                "[10]",
                "TITLELESS_WRONG_VOLPAGE",
                ["[10]", "Einstein", "Phys. Rev. 48"],
                "The EPR paper is Phys. Rev. 47, 777 (1935); volume 48 page 777 is an unrelated erratum.",
                "Change the volume to 47 (doi:10.1103/PhysRev.47.777).",
                doi="10.1103/physrev.47.777",
            ),
            ok("[11]", ["[11]", "Devlin", "BERT"], "10.18653/v1/N19-1423"),
            claim(
                "[4]",
                "CLAIM_NUMBER",
                ["[4]", "Krizhevsky", "ImageNet"],
                ["1,200만", "1200만", "12 million"],
                "1,200만 장의 고해상도 이미지",
                "the 1.2 million high-resolution images in the ImageNet LSVRC-2010 contest",
                "10.1145/3065386",
            ),
            claim(
                "[4]",
                "CLAIM_DIRECTION",
                ["[4]", "Krizhevsky", "ImageNet"],
                ["20% 이상", "20%"],
                "테스트 데이터에서 top-5 오류율이 20% 이상",
                "top-1 and top-5 error rates of 37.5% and 17.0%",
                "10.1145/3065386",
            ),
        ],
    },
}


def main() -> None:
    for name, manuscript in MANUSCRIPTS.items():
        for index, item in enumerate(manuscript["items"], start=1):
            item["id"] = f"{name}#{index:02d}"
            item["expected"] = "FLAG" if item["type"] in ERROR_TYPES else "NOT_FLAG"
    counts: dict[str, int] = {}
    for manuscript in MANUSCRIPTS.values():
        for item in manuscript["items"]:
            counts[item["type"]] = counts.get(item["type"], 0) + 1
    payload = {
        "description": "Planted errors and correct references in the e2e manuscripts; see README.md.",
        "error_types": list(ERROR_TYPES),
        "counts": counts,
        "manuscripts": MANUSCRIPTS,
    }
    (HERE / "truth.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
