"""Write the v2 manuscripts and truth.json from sources.json (frozen CrossRef/arXiv metadata).

Every real paper cited in v2 is obscure: published 2025-2026 (except two retracted 2023-2024
papers), with at most 30 citations in CrossRef (`is-referenced-by-count`) when fetched on
2026-10-09. The author of the set did not recognise any of them before fetching their
records. Planted errors are applied here, so the manuscripts and the truth file cannot drift
apart. Run once; the outputs are committed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
FETCHED = "2026-10-09"

JOURNAL_FIXES = {
    "10.1097/md.0000000000050120": ("Medicine", "Medicine (Baltimore)"),
    "10.1213/xaa.0000000000001891": ("A&A Practice", "A A Pract"),
    "10.1063/5.0326956": ("APL Materials", "APL Mater."),
    "10.51435/turkjac.1760136": ("Turkish Journal of Analytical Chemistry", "Turk. J. Anal. Chem."),
}
PHYSICS_ABBREV = {
    "10.1088/1361-6463/add7e9": "J. Phys. D: Appl. Phys.",
    "10.1088/1361-6595/adaa9b": "Plasma Sources Sci. Technol.",
    "10.1088/1361-6595/ae5d6a": "Plasma Sources Sci. Technol.",
    "10.3390/nano16090558": "Nanomaterials",
    "10.3390/plasma9030036": "Plasma",
    "10.3390/ma19143012": "Materials",
    "10.1063/5.0326956": "APL Mater.",
    "10.1007/s40042-026-01566-z": "J. Korean Phys. Soc.",
    "10.1007/s40042-026-01570-3": "J. Korean Phys. Soc.",
    "10.1007/s40042-025-01537-w": "J. Korean Phys. Soc.",
    "10.1007/s10904-024-03325-8": "J. Inorg. Organomet. Polym. Mater.",
}


# --- metadata helpers --------------------------------------------------------------

def src(doi: str) -> dict:
    return SOURCES[doi.lower()]


def journal(doi: str) -> str:
    if doi.lower() in JOURNAL_FIXES:
        return JOURNAL_FIXES[doi.lower()][0]
    return src(doi)["journal"].replace("&amp;", "&")


def short_journal(doi: str) -> str:
    if doi.lower() in JOURNAL_FIXES:
        return JOURNAL_FIXES[doi.lower()][1]
    return src(doi)["short"] or journal(doi)


def year(doi: str) -> int:
    years = src(doi)["years"]
    return years.get("published-print") or years.get("issued") or years.get("published-online")


def pages(doi: str) -> str:
    record = src(doi)
    value = record["article_number"] or record["page"] or ""
    if record["article_number"] and record["page"] and "-" not in record["page"]:
        value = record["page"]
    if value.startswith("v12i21"):
        value = "e78091"
    return value.replace("-", "–")


def first_page(doi: str) -> str:
    return pages(doi).split("–")[0]


def title(doi: str) -> str:
    text = src(doi)["title"]
    text = re.sub(r"^RETRACTED(?: ARTICLE)?:\s*", "", text)
    text = text.replace("&lt;sup&gt;", "").replace("&lt;/sup&gt;", "").replace("‐", "-")
    text = re.sub(r"\$\$\{\\text\{CsV\}\}_\{2\}\{\\text\{Se\}\}_\{2\}\\text\{O\}\$\$\s*", "", text)
    return " ".join(text.split())


def authors(doi: str) -> list[tuple[str, str]]:
    return [(family, given) for family, given in src(doi)["authors"]]


def initials(given: str, spaced: bool = True) -> str:
    parts = [p for p in re.split(r"[\s.]+", given) if p]
    out = []
    for part in parts:
        if "-" in part:
            out.append("-".join(piece[0] + "." for piece in part.split("-") if piece))
        else:
            out.append(part[0] + ".")
    return (" " if spaced else "").join(out)


def swap_first_two(names: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [names[1], names[0], *names[2:]]


# --- citation styles ---------------------------------------------------------------

def apa(doi: str, *, names=None, yr=None, cite_doi=None, ttl=None) -> str:
    names = names or authors(doi)
    def one(name):
        family, given = name
        return f"{family}, {initials(given)}" if given else family
    if len(names) == 1:
        author_text = one(names[0])
    elif len(names) <= 7:
        author_text = ", ".join(one(n) for n in names[:-1]) + ", & " + one(names[-1])
    else:
        author_text = ", ".join(one(n) for n in names[:6]) + ", … " + one(names[-1])
    record = src(doi)
    vol = record["volume"]
    issue = f"({record['issue']})" if record["issue"] else ""
    return (f"{author_text} ({yr or year(doi)}). {ttl or title(doi)}. *{journal(doi)}*, {vol}{issue}, {pages(doi)}. "
            f"https://doi.org/{cite_doi or record['doi']}")


def vancouver(doi: str, *, names=None, yr=None, cite_doi=None, with_doi=True) -> str:
    names = names or authors(doi)
    def one(name):
        family, given = name
        return f"{family} {initials(given, spaced=False).replace('.', '')}" if given else family
    author_text = ", ".join(one(n) for n in names[:6]) + (", et al" if len(names) > 6 else "")
    record = src(doi)
    issue = f"({record['issue']})" if record["issue"] else ""
    text = f"{author_text}. {title(doi)}. {short_journal(doi).rstrip('.')}. {yr or year(doi)};{record['volume']}{issue}:{pages(doi)}."
    if with_doi:
        text += f" doi:{cite_doi or record['doi']}"
    return text


def ieee(doi: str, *, names=None, yr=None, cite_doi=None) -> str:
    names = names or authors(doi)
    def one(name):
        family, given = name
        return f"{initials(given)} {family}" if given else family
    if len(names) > 6:
        author_text = one(names[0]) + " et al."
    elif len(names) == 1:
        author_text = one(names[0])
    elif len(names) == 2:
        author_text = f"{one(names[0])} and {one(names[1])}"
    else:
        author_text = ", ".join(one(n) for n in names[:-1]) + ", and " + one(names[-1])
    record = src(doi)
    number = f", no. {record['issue']}" if record["issue"] else ""
    pp = pages(doi)
    pp_text = f"pp. {pp}" if "–" in pp else f"Art. no. {pp}"
    return (f'{author_text}, "{title(doi)}," *{short_journal(doi)}*, vol. {record["volume"]}{number}, {pp_text}, '
            f"{yr or year(doi)}, doi: {cite_doi or record['doi']}.")


def physics(doi: str, *, volume=None, page=None) -> str:
    names = authors(doi)
    def one(name):
        family, given = name
        return f"{initials(given)} {family}" if given else family
    if len(names) <= 2:
        author_text = " and ".join(one(n) for n in names)
    else:
        author_text = one(names[0]) + " et al."
    record = src(doi)
    return f"{author_text}, {PHYSICS_ABBREV[doi.lower()]} {volume or record['volume']}, {page or first_page(doi)} ({year(doi)})."


def korean_pk(doi: str, *, yr=None, cite_doi=None, ttl=None) -> str:
    names = authors(doi)
    def one(name):
        family, given = name
        return f"{family}, {initials(given)}"
    author_text = one(names[0]) + (f" 외 {len(names) - 1}인" if len(names) > 1 else "")
    record = src(doi)
    return (f'{author_text}, "{ttl or record["original_title"]}", 폴리머, {record["volume"]}({record["issue"]}), '
            f"{pages(doi)} ({yr or year(doi)}). https://doi.org/{cite_doi or record['doi']}")


def bibtex(key: str, doi: str, *, names=None, yr=None, cite_doi=None, with_doi=True) -> str:
    names = names or authors(doi)
    record = src(doi)
    author_text = " and ".join(f"{family}, {given}" if given else f"{{{family}}}" for family, given in names)
    fields = [
        ("author", author_text),
        ("title", "{" + title(doi) + "}"),
        ("journal", journal(doi).replace("&", "\\&")),
        ("volume", record["volume"]),
        ("number", record["issue"]),
        ("pages", pages(doi).replace("–", "--")),
        ("year", str(yr or year(doi))),
    ]
    if with_doi:
        fields.append(("doi", cite_doi or record["doi"]))
    body = ",\n".join(f"  {name:<7} = {{{value}}}" for name, value in fields if value)
    return f"@article{{{key},\n{body}\n}}"


def arxiv_ref(arxiv_id: str, style: str) -> str:
    record = SOURCES["arxiv:" + arxiv_id]
    names = record["authors"]
    yr = record["published"][:4]
    if style == "apa":
        def one(full):
            parts = full.split()
            return f"{parts[-1]}, {' '.join(p[0] + '.' for p in parts[:-1])}"
        author_text = ", ".join(one(n) for n in names[:6]) + (", …" if len(names) > 6 else "")
        if len(names) <= 6 and len(names) > 1:
            author_text = ", ".join(one(n) for n in names[:-1]) + ", & " + one(names[-1])
        return f"{author_text} ({yr}). {record['title']}. arXiv:{arxiv_id}."
    if style == "physics":
        first = names[0].split()
        return f"{' '.join(p[0] + '.' for p in first[:-1])} {first[-1]} et al., arXiv:{arxiv_id} ({yr})."
    if style == "ieee":
        first = names[0].split()
        lead = f"{' '.join(p[0] + '.' for p in first[:-1])} {first[-1]}" + (" et al." if len(names) > 2 else "")
        return f'{lead}, "{record["title"]}," arXiv:{arxiv_id}, {yr}.'
    if style == "bib":
        author_text = " and ".join(f"{n.split()[-1]}, {' '.join(n.split()[:-1])}" for n in names)
        return (f"@misc{{{arxiv_id.replace('.', '_')},\n  author  = {{{author_text}}},\n  title   = {{{record['title']}}},\n"
                f"  year    = {{{yr}}},\n  eprint  = {{{arxiv_id}}},\n  archivePrefix = {{arXiv}}\n}}")
    raise ValueError(style)


def author_date(doi: str, names=None, yr=None) -> str:
    names = names or authors(doi)
    if len(names) == 1:
        lead = names[0][0]
    elif len(names) == 2:
        lead = f"{names[0][0]} & {names[1][0]}"
    else:
        lead = f"{names[0][0]} et al."
    return f"{lead}, {yr or year(doi)}"


# --- truth item helpers --------------------------------------------------------------

def meta(doi: str) -> dict:
    record = src(doi)
    return {"truth_doi": record["doi"], "cited_by": record["cited_by"], "year": year(doi),
            "years": record["years"], "recall_check": "not recognised before fetching (author of the set)"}


def ok(ref, match, doi, **extra):
    return {"ref": ref, "type": "OK", "match": match, **meta(doi), **extra}


def unindexed(ref, match, source, **extra):
    return {"ref": ref, "type": "UNINDEXED_OK", "match": match, "truth_doi": None, "source": source, **extra}


def error(ref, kind, match, problem, fix, doi=None, **extra):
    item = {"ref": ref, "type": kind, "match": match, "problem": problem, "fix": fix}
    if doi:
        item.update(meta(doi))
    else:
        item["truth_doi"] = None
    item.update(extra)
    return item


def claim(ref, kind, match, value, text, abstract, doi):
    return {"ref": ref, "type": kind, "match": match, "value": value, "claim_text": text,
            "abstract_says": abstract, "abstract_source": "crossref", **meta(doi)}


THESIS_IPMC = ('이장우, "나피온계 IPMC의 무전해 도금 방법 및 내부 용액에 관한 연구", 석사학위논문, 건국대학교 대학원, 2006.',
               "https://m.riss.kr/search/detail/DetailView.do?p_mat_type=be54d9b8bc7cdb09&control_no=5fbf1da37fc3dc6dffe0bdc3ef48d419")
THESIS_NCM = ("박성민, \"니켈계 리튬 전이금속 산화물의 열분해 메커니즘에 대한 연구\", 박사학위논문, 연세대학교 대학원, 2013.",
              "https://m.riss.kr/search/detail/DetailView.do?control_no=fe70ea7986d1a8f9ffe0bdc3ef48d419&p_mat_type=be54d9b8bc7cdb09")


# --- M1: dielectric elastomer actuators, English, APA --------------------------------------

def m1():
    D = {
        "veloso": "10.1088/1361-665x/adb18d", "zeng": "10.1002/app.70135", "anna": "10.1002/admt.202502275",
        "wang_ere": "10.1088/2631-8695/ae924e", "tang": "10.1002/pssa.70504", "mei": "10.1002/adem.202502157",
        "gurjar": "10.1088/1361-665x/aea942", "niu": "10.1088/1361-665x/ae7b8f", "wang_sms": "10.1088/1361-665x/add067",
        "neu": "10.3390/act14110544", "zhang": "10.3390/technologies14010068", "guan": "10.1371/journal.pone.0352654",
    }
    neu_names = swap_first_two(authors(D["neu"]))
    fab = ("Hartmann, L., Osei, K., & Brandt, M. (2025). Electrode-free dielectric elastomer actuators using ionic skin "
           "layers for haptic sleeves. *Smart Materials and Structures*, 34(7), 075012. "
           "https://doi.org/10.1088/1361-665X/ade5f1")
    refs = {
        "veloso": apa(D["veloso"]), "zeng": apa(D["zeng"]), "anna": apa(D["anna"]), "wang_ere": apa(D["wang_ere"]),
        "tang": apa(D["tang"]), "mei": apa(D["mei"]), "gurjar": apa(D["gurjar"]), "niu": apa(D["niu"], yr=2023),
        "wang_sms": apa(D["wang_sms"]), "neu": apa(D["neu"], names=neu_names), "zhang": apa(D["zhang"], cite_doi=D["guan"]),
        "fab": fab, "arxiv": arxiv_ref("2608.00369", "apa"),
    }
    c = {k: f"({author_date(v)})" for k, v in D.items()}
    c["niu"] = f"({author_date(D['niu'], yr=2023)})"
    c["neu"] = f"({author_date(D['neu'], names=neu_names)})"
    c["fab"] = "(Hartmann et al., 2025)"
    c["arxiv"] = "(Remenar et al., 2026)"
    text = f"""# Low-voltage dielectric elastomer actuators for wearable counterpressure and haptic devices

## Introduction

Dielectric elastomer actuators (DEAs) are used in soft robotics, medical devices, and wearable electronics {c['mei']}. A DEA-based mechanical counterpressure cuff for space suits reached a counterpressure of 19.52 MPa with a response time of 0.7 s {c['veloso']}. Fillers raise the permittivity of silicone matrices: onion-like carbons gave a maximum actuated strain of 25.9% at 32 kV/mm {c['zeng']}, and MXene/onion-like-carbon hybrids kept the composites stable up to about 400 °C {c['tang']}. Dielectric liquid crystal elastomer actuators deliver enhanced work output only under small loads below 1.5 MPa {c['anna']}.

At the device level, a rolled DEA drove a soft crawling robot at 4 mm/s at 7 kV and 2 Hz {c['wang_ere']}, in-plane DEAs enabled resonant locomotion of thin hybrid robots {c['wang_sms']}, and bistable actuators were built by combining DEAs with shape memory polymer composites {c['niu']}. Arrays of DEAs provide haptic feedback in wearables {c['neu']}, conical DEA generators harvest wave energy {c['gurjar']}, and DEA lenses give tunable focal length {c['zhang']}. Electrode-free ionic skin layers have also been proposed for haptic sleeves {c['fab']}, and robotic systems now automate DEA manufacturing {c['arxiv']}.

## Results and discussion

Our three-layer silicone actuators with carbon-black electrodes reached 6% areal strain at 3.5 kV, comparable to filled single-layer films {c['zeng']} but at lower field.

## References

""" + "\n\n".join(refs[k] for k in sorted(refs, key=lambda k: refs[k].lower())) + "\n"
    items = [
        claim("Veloso et al., 2025", "CLAIM_UNIT", ["Veloso"], ["19.52 MPa", "MPa"],
              "a counterpressure of 19.52 MPa", "The final cuff design achieves an MCP of 19.52 kPa", D["veloso"]),
        claim("Zeng & Tang, 2026", "CLAIM_NUMBER", ["Zeng"], ["25.9"],
              "a maximum actuated strain of 25.9% at 32 kV/mm",
              "it delivers a maximum actuated strain of 15.9% at a low electric field of 32 kV/mm", D["zeng"]),
        claim("Annapooranan et al., 2026", "CLAIM_DIRECTION", ["Annapooranan"], ["below 1.5", "small loads"],
              "enhanced work output only under small loads below 1.5 MPa",
              "significantly enhanced work output under large loads (>1.5 MPa)", D["anna"]),
        claim("Wang et al., 2026", "CLAIM_OK", ["4 mm/s"], ["4 mm/s"], "4 mm/s at 7 kV and 2 Hz",
              "maximum measured crawling speed of 4 mm s−1 at 7 kV and 2 Hz", D["wang_ere"]),
        ok("Veloso et al., 2025", ["Veloso"], D["veloso"]),
        ok("Zeng & Tang, 2026", ["Zeng"], D["zeng"]),
        ok("Annapooranan et al., 2026", ["Annapooranan"], D["anna"]),
        ok("Wang et al., 2026 (crawling robot)", ["crawling"], D["wang_ere"]),
        ok("Tang & Zeng, 2026", ["Tang"], D["tang"]),
        ok("Mei et al., 2026", ["Mei"], D["mei"]),
        ok("Gurjar & Patra, 2026", ["Gurjar"], D["gurjar"]),
        error("Niu et al., 2023", "WRONG_YEAR", ["Niu"], "Smart Mater. Struct. 35(6) 065047 was published in 2026, not 2023.",
              "Change the year to 2026.", D["niu"], cited_year=2023, true_year=2026),
        ok("Wang et al., 2025 (in-plane DEA robot)", ["in-plane", "add067"], D["wang_sms"]),
        error(f"{neu_names[0][0]} et al., 2025", "WRONG_AUTHOR", [neu_names[0][0], "Neu"],
              f"First author is Neu, J.; the reference lists {neu_names[0][0]} first.",
              "Put Neu, J. first.", D["neu"]),
        error("Zhang et al., 2026", "DOI_SWAP", ["Zhang", "lens", "pone.0352654"],
              "The DOI 10.1371/journal.pone.0352654 is Guan et al. (2026), a PLOS One soft-gripper paper; the lens paper is "
              "10.3390/technologies14010068.", "Use 10.3390/technologies14010068.", D["zhang"], cited_doi=D["guan"]),
        error("Hartmann et al., 2025", "FAB_DOI", ["Hartmann", "ade5f1"],
              "DOI 10.1088/1361-665X/ade5f1 does not exist (CrossRef 404, doi.org 'DOI does not exist'); no such paper.",
              "Remove the reference and the sentence."),
        unindexed("Remenar et al., 2026", ["Remenar", "2608.00369"], "https://arxiv.org/abs/2608.00369"),
    ]
    return text, None, items


# --- M2: ionic polymer actuators and ionogels, English, Vancouver ------------------------------

def m2():
    order = ["lv", "chen", "zamp", "jian", "zhangc", "lu", "reinoso", "tyagi", "ahmed", "lin", "wang", "fab"]
    D = {"lv": "10.1002/app.57410", "chen": "10.3390/mi17080983", "zamp": "10.3390/jcs10010058",
         "jian": "10.3390/polym17070921", "zhangc": "10.1016/j.carbpol.2025.123278", "lu": "10.1002/smll.202511861",
         "reinoso": "10.1002/pol.20250372", "tyagi": "10.1002/app.57294", "ahmed": "10.1177/09673911251327811",
         "lin": "10.1002/smll.202512882", "wang": "10.1002/cssc.71126"}
    n = {k: i + 1 for i, k in enumerate(order)}
    tyagi_names = swap_first_two(authors(D["tyagi"]))
    refs = {k: vancouver(v) for k, v in D.items()}
    refs["reinoso"] = vancouver(D["reinoso"], yr=2022)
    refs["tyagi"] = vancouver(D["tyagi"], names=tyagi_names)
    refs["fab"] = ("Okafor B, Tanaka R, Weiss H. Recycled platinum electrodes for Nafion-free IPMC bending "
                   "actuators. Sens Actuators B Chem. 2025;412:135902.")
    text = f"""# Ionic polymer actuators and ionogel sensors for low-voltage soft robotics

## Introduction

Ionic electroactive polymers bend at a few volts, which makes them attractive for soft robotics. Chitosan biogel actuators crosslinked with 0.1 wt% genipin produced an output force of 2.93 N [{n['lv']}], and ionic polymer–metal composites without Nafion have been demonstrated with recycled platinum electrodes [{n['fab']}]. Porous ionogel foams give pressure sensors a normalized sensitivity of 26.45 kPa⁻¹ between 2 and 10 kPa [{n['chen']}], and cellulose ionogels combine 1.28 MPa tensile strength with 573% elongation [{n['jian']}]. Alginate-based ion-conductive hydrogel sensors [{n['zhangc']}] and thermoelectric–piezoionic ionogels [{n['lu']}] extend these devices to sensing and multimodal energy harvesting.

For dielectric layers, surface-functionalizing BaTiO3 with APEOPTES lowered the breakdown strength of PDMS nanocomposites from 42.1 to 33.8 kV/mm [{n['zamp']}]. Electroactive PVDF–CoFe2O4 nanocomposites combine microwave absorption with energy harvesting [{n['tyagi']}], and hematite/chitosan nanocomposite films have been characterized for thermal stability, mechanical strength, and ionic conductivity [{n['ahmed']}].

## Electrolyte layer

Our gel electrolyte follows the functionalized-filler strategy for Li-polymer composite electrolytes [{n['reinoso']}] and the controllable crosslinking route of [{n['lin']}], with a PTFE support as in [{n['wang']}].

## References

""" + "\n".join(f"{i}. {refs[k]}" for i, k in enumerate(order, start=1)) + "\n"
    r = lambda k: f"[{n[k]}]"
    items = [
        claim(r("lv"), "CLAIM_UNIT", [r("lv"), "Lv", "genipin"], ["2.93 N"], "an output force of 2.93 N",
              "a 0.1 wt% crosslinking concentration leads to a 2.68-fold increase in output force (2.93 mN)", D["lv"]),
        claim(r("chen"), "CLAIM_NUMBER", [r("chen"), "Chen"], ["26.45"], "a normalized sensitivity of 26.45 kPa⁻¹",
              "the sensor achieves a high normalized sensitivity of 62.45 kPa−1 (2–10 kPa)", D["chen"]),
        claim(r("zamp"), "CLAIM_DIRECTION", [r("zamp"), "Zamperlin"], ["lowered", "42.1 to 33.8"],
              "lowered the breakdown strength of PDMS nanocomposites from 42.1 to 33.8 kV/mm",
              "increasing permittivity from 2.8 to 7.5, EBD from 33.8 to 42.1 kV/mm", D["zamp"]),
        claim(r("jian"), "CLAIM_OK", ["573"], ["573"], "1.28 MPa tensile strength with 573% elongation",
              "robust mechanical strength (1.28 MPa tensile strength with 573% elongation)", D["jian"]),
        ok(r("lv"), [r("lv"), "Lv"], D["lv"]),
        ok(r("chen"), [r("chen"), "Chen Y"], D["chen"]),
        ok(r("zamp"), [r("zamp"), "Zamperlin"], D["zamp"]),
        ok(r("jian"), [r("jian"), "Jian"], D["jian"]),
        error(r("zhangc"), "RETRACTED", [r("zhangc"), "Zhang L", "alginate"],
              "Retracted (CrossRef updated-by: retraction).", "Remove it.", D["zhangc"]),
        ok(r("lu"), [r("lu"), "Lu R"], D["lu"]),
        error(r("reinoso"), "WRONG_YEAR", [r("reinoso"), "Reinoso"], "J Polym Sci 63(18) was published in 2025, not 2022.",
              "Change the year to 2025.", D["reinoso"], cited_year=2022, true_year=2025),
        error(r("tyagi"), "WRONG_AUTHOR", [r("tyagi"), "Chauhan", "Tyagi"], "First author is Tyagi S; the reference lists Chauhan D first.",
              "Put Tyagi S first.", D["tyagi"]),
        ok(r("ahmed"), [r("ahmed"), "Ahmed"], D["ahmed"]),
        ok(r("lin"), [r("lin"), "Lin M"], D["lin"]),
        ok(r("wang"), [r("wang"), "Wang D"], D["wang"]),
        error(r("fab"), "FAB_NODOI", [r("fab"), "Okafor", "Nafion-free"], "No such paper (no CrossRef record with this title).",
              "Remove the reference and the sentence.",
              cited_title="Recycled platinum electrodes for Nafion-free IPMC bending actuators"),
    ]
    return text, None, items


# --- M3: crystallization and thermal analysis, LaTeX + BibTeX --------------------------------

def m3():
    D = {"sonn": "10.1002/app.57209", "merl": "10.1002/pol.20250882", "chenp": "10.1002/pat.70664", "tan": "10.3390/s26092680",
         "xie": "10.3390/polym17172390", "yang": "10.1002/app.57524", "arslan": "10.1002/pc.71040", "li": "10.1002/adem.202503161",
         "xavier": "10.1002/pen.26716"}
    keys = {"sonn": "sonnendecker2025", "merl": "merlonghi2026", "chenp": "chen2026pllla", "tan": "tan2026pa66",
            "xie": "xie2025tga", "yang": "yang2025foam", "arslan": "arslan2026pps", "li": "li2026lattice", "xavier": "xavier2024oxide"}
    arslan_names = swap_first_two(authors(D["arslan"]))
    bib = [bibtex(keys[k], D[k]) for k in ("sonn", "chenp", "tan", "xie", "yang", "li", "xavier")]
    bib.append(bibtex(keys["merl"], D["merl"], cite_doi="10.1002/pc.70772"))
    bib.append(bibtex(keys["arslan"], D["arslan"], names=arslan_names))
    bib.append("@article{novak2025,\n  author  = {Nov{\\'a}k, Petra and Ferreira, Lu{\\'i}s},\n"
               "  title   = {{Isothermal cold crystallization of 3D-printed PLA/PBS blends studied by modulated DSC}},\n"
               "  journal = {Journal of Applied Polymer Science},\n  volume  = {142},\n  number  = {28},\n"
               "  pages   = {e58913},\n  year    = {2025},\n  doi     = {10.1002/app.58913}\n}")
    bib.append(arxiv_ref("2604.11706", "bib"))
    tex = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{siunitx}
\title{Crystallization and thermal stability of semicrystalline polymers for additive manufacturing}
\author{}
\date{}
\begin{document}
\maketitle

\section{Introduction}
Crystallinity controls the stiffness, permeability, and thermal resistance of printed semicrystalline polymers. In PVDF topcoats, the plasticizer di(propylene glycol) dibenzoate reduced the degree of crystallinity from 34\% to 31\% while preserving film integrity \cite{sonnendecker2025}. Fast-scanning chip calorimetry gave an apparent activation energy of \SI{172.3}{\joule\per\mole} for homogeneous-nucleation cold crystallization of PA66 at low heating rates \cite{tan2026pa66}, and TGA-based kinetic models predict a service lifetime of 61 years at \SI{80}{\celsius} for SGP membranes \cite{xie2025tga}. Boron nitride nanosheets and melt crystallization raise the crystallinity of PLLA \cite{chen2026pllla}, and raising the powder bed temperature in laser powder bed fusion to \SI{130}{\celsius} increased the crystallinity of PLLA lattices from 23.46\% to 34.93\% \cite{li2026lattice}. Crystallinity also governs hydrogen transport in polyethylene \cite{merlonghi2026}, cold crystallization of printed PLA/PBS blends \cite{novak2025}, and the cell structure of PLLA/PDLA foams \cite{yang2025foam}. Recycled carbon fibre and thermal black change the crystallization kinetics and microstructure of printed PPS \cite{arslan2026pps}, and NiO/NiS-modified poly(3-methylthiophene) nanocomposites have been proposed for energy storage \cite{xavier2024oxide}. Simulations show that pre-shear and dispersity shift crystallization in model polymers \cite{2604_11706}.

\section{Results}
Our printed PLLA reached 31\% crystallinity after annealing at \SI{110}{\celsius}, between the values reported for lattices printed at 101 and \SI{130}{\celsius} bed temperatures \cite{li2026lattice}.

\bibliographystyle{unsrt}
\bibliography{references}
\end{document}
"""
    items = [
        claim("sonnendecker2025", "CLAIM_DIRECTION", ["sonnendecker2025", "Sonnendecker"], ["34% to 31%", "34\\% to 31\\%", "reduced"],
              "the plasticizer di(propylene glycol) dibenzoate reduced the degree of crystallinity from 34% to 31%",
              "P2 raised the degree of crystallinity from 31% in the reference film to 34%", D["sonn"]),
        claim("tan2026pa66", "CLAIM_UNIT", ["tan2026pa66", "Tan"], ["172.3 J", "J/mol", "\\joule\\per\\mole"],
              "an apparent activation energy of 172.3 J/mol", "reaching 172.3 kJ·mol−1", D["tan"]),
        claim("xie2025tga", "CLAIM_NUMBER", ["xie2025tga", "Xie"], ["61 years", "61"],
              "a service lifetime of 61 years at 80 °C", "the service lifetime of the SGP membrane sample is 16 years at 80 °C",
              D["xie"]),
        claim("li2026lattice", "CLAIM_OK", ["23.46", "34.93"], ["34.93"], "increased the crystallinity of PLLA lattices from 23.46% to 34.93%",
              "the crystallinity increases from 23.46% to 34.93%", D["li"]),
        ok("sonnendecker2025", ["sonnendecker2025"], D["sonn"]),
        error("merlonghi2026", "DOI_SWAP", ["merlonghi2026", "Merlonghi"],
              "The DOI 10.1002/pc.70772 is Liu et al. (2026), basalt fibre composites; Merlonghi et al. is 10.1002/pol.20250882.",
              "Use 10.1002/pol.20250882.", D["merl"], cited_doi="10.1002/pc.70772"),
        ok("chen2026pllla", ["chen2026pllla"], D["chenp"]),
        ok("tan2026pa66", ["tan2026pa66"], D["tan"]),
        ok("xie2025tga", ["xie2025tga"], D["xie"]),
        ok("yang2025foam", ["yang2025foam"], D["yang"]),
        error("arslan2026pps", "WRONG_AUTHOR", ["arslan2026pps"], "First author is Arslan, D.; the entry lists Mihai, M. first.",
              "Put Arslan, Dogan first.", D["arslan"]),
        ok("li2026lattice", ["li2026lattice"], D["li"]),
        error("xavier2024oxide", "RETRACTED", ["xavier2024oxide", "Xavier"], "Retracted (CrossRef updated-by: retraction).",
              "Remove it.", D["xavier"]),
        error("novak2025", "FAB_DOI", ["novak2025", "app.58913", "PLA/PBS"],
              "DOI 10.1002/app.58913 does not exist; no such paper.", "Remove the entry and the sentence."),
        unindexed("2604_11706", ["2604_11706", "2604.11706", "Koulaxizis"], "https://arxiv.org/abs/2604.11706"),
    ]
    return tex, "\n\n".join(bib) + "\n", items


# --- M4: Korean polymer journals, Korean --------------------------------------------------

def m4():
    order = ["choi", "xu", "jing", "koo", "lee", "hong", "kim", "zhan", "ben", "swap", "fab", "thesis"]
    D = {"choi": "10.7317/pk.2025.49.4.450", "xu": "10.7317/pk.2025.49.5.536", "jing": "10.7317/pk.2025.49.1.17",
         "koo": "10.7317/pk.2025.49.2.205", "lee": "10.7317/pk.2025.49.3.325", "hong": "10.7317/pk.2025.49.5.626",
         "kim": "10.7317/pk.2025.49.4.387", "zhan": "10.3390/act14040171", "ben": "10.3390/polym17040494",
         "swap": "10.7317/pk.2025.49.5.556"}
    n = {k: i + 1 for i, k in enumerate(order)}
    refs = {k: korean_pk(D[k]) for k in ("choi", "xu", "koo", "lee", "hong", "kim")}
    refs["jing"] = korean_pk(D["jing"], yr=2023)
    refs["zhan"] = apa(D["zhan"])
    refs["ben"] = apa(D["ben"])
    refs["swap"] = ('정유진, 한도윤, "형상기억 폴리우레탄 섬유의 열적·기계적 특성", 폴리머, 49(5), 556–563 (2025). '
                    "https://doi.org/10.7317/pk.2025.49.5.556")
    refs["fab"] = ('김민준, 이하은, "이온성 액체 기반 고분자 구동기의 저전압 굽힘 특성", 폴리머, 49(6), 781–788 (2025). '
                   "https://doi.org/10.7317/pk.2025.49.6.781")
    refs["thesis"] = THESIS_IPMC[0]
    text = f"""# 결정성 이온젤과 고분자 복합재 기반 구동·감지 소재의 최근 연구 동향

## 서론

결정성 이온젤은 합성 후 스트레인 센서로 응용되었고[{n['choi']}], MXene/에폭시 복합재의 경화 동역학도 분석되었다[{n['xu']}]. 초임계 기반 전단 탈황과 탄산칼슘 개질로 재생 고무의 특성을 높인 연구[{n['jing']}], 전기전도성 산화주석으로 충전한 폴리(4-메틸-1-펜텐) 나노복합체[{n['koo']}], 표면 개질 셀룰로오스 나노섬유와 초고분자량 폴리프로필렌 복합재[{n['lee']}], 카복실화로 충격강도를 높인 PPS[{n['hong']}], 아연 이온을 방출하는 생체활성 하이드로젤[{n['kim']}]도 보고되었다.

## 구동 소재

광응답 액정 엘라스토머(LCE) 코일은 지름 375 mm로 제작되었으며, 455 nm 가시광을 쬐면 30% 늘어난다[{n['zhan']}]. 습식 방사로 만든 LCE 섬유는 자기 무게의 140배를 들어 올렸다[{n['ben']}]. 국내에서는 형상기억 폴리우레탄 섬유의 열적·기계적 특성[{n['swap']}]과 이온성 액체 기반 고분자 구동기의 저전압 굽힘 특성[{n['fab']}]이 연구되었고, 나피온계 IPMC의 무전해 도금 방법은 학위논문으로 정리되었다[{n['thesis']}].

## 참고문헌

""" + "\n\n".join(f"[{i}] {refs[k]}" for i, k in enumerate(order, start=1)) + "\n"
    r = lambda k: f"[{n[k]}]"
    items = [
        claim(r("zhan"), "CLAIM_UNIT", [r("zhan"), "Zhan", "LCE 코일"], ["375 mm"], "지름 375 mm로 제작",
              "photopolymerized under UV light to form an LCE coil with a diameter of 375 µm", D["zhan"]),
        claim(r("zhan"), "CLAIM_DIRECTION", [r("zhan"), "Zhan", "455 nm"], ["늘어난다", "30% 늘", "팽창"],
              "455 nm 가시광을 쬐면 30% 늘어난다", "30% contraction to 455 nm visible light", D["zhan"]),
        claim(r("ben"), "CLAIM_OK", ["140배"], ["140"], "자기 무게의 140배를 들어 올렸다",
              "lifting up to 140 times their own weight", D["ben"]),
        ok(r("choi"), [r("choi"), "Choi"], D["choi"]),
        ok(r("xu"), [r("xu"), "Xu"], D["xu"]),
        error(r("jing"), "WRONG_YEAR", [r("jing"), "Jing"], "폴리머 49(1) 17–26은 2025년 발행, 2023년이 아님.",
              "연도를 2025로 고친다.", D["jing"], cited_year=2023, true_year=2025),
        ok(r("koo"), [r("koo"), "Koo"], D["koo"]),
        ok(r("lee"), [r("lee"), "Lee, J."], D["lee"]),
        ok(r("hong"), [r("hong"), "Hong"], D["hong"]),
        ok(r("kim"), [r("kim"), "Kim, Y."], D["kim"]),
        ok(r("zhan"), [r("zhan"), "Zhan"], D["zhan"]),
        ok(r("ben"), [r("ben"), "Benecke"], D["ben"]),
        error(r("swap"), "DOI_SWAP", [r("swap"), "정유진", "형상기억"],
              "DOI 10.7317/pk.2025.49.5.556은 Lee 외 'Pyridoquinolinedione as a New Building Block…'(유기태양전지)이며, "
              "인용된 제목·저자의 논문은 없음.", "올바른 문헌으로 바꾸거나 삭제한다.", D["swap"]),
        error(r("fab"), "FAB_DOI", [r("fab"), "김민준", "pk.2025.49.6.781"],
              "DOI 10.7317/pk.2025.49.6.781은 존재하지 않음(CrossRef 404, doi.org 'DOI does not exist').",
              "참고문헌과 해당 문장을 삭제한다."),
        unindexed(r("thesis"), [r("thesis"), "이장우"], THESIS_IPMC[1]),
    ]
    return text, None, items


# --- M5: PVDF and liquid crystal elastomers, English, IEEE ---------------------------------

def m5():
    order = ["parth", "toru", "sezer", "luo", "ben26", "ali", "yang", "sujitha", "fab", "arxiv"]
    D = {"parth": "10.1002/est2.70461", "toru": "10.3390/polym18050617", "sezer": "10.51435/turkjac.1760136",
         "luo": "10.1002/adma.202516047", "ben26": "10.1038/s41598-026-54707-6", "ali": "10.1002/ente.202502400",
         "yang": "10.3390/app16199732", "sujitha": "10.1007/s00289-023-04888-1"}
    n = {k: i + 1 for i, k in enumerate(order)}
    refs = {k: ieee(v) for k, v in D.items()}
    refs["yang"] = ieee(D["yang"], yr=2023)
    refs["fab"] = ('M. Ortega and J. Lindqvist, "Corona-poled PVDF/LCE bilayer fibres for self-sensing artificial muscles," '
                   "*Polymers*, vol. 18, no. 9, Art. no. 1377, 2026, doi: 10.3390/polym18091377.")
    refs["arxiv"] = arxiv_ref("2510.20370", "ieee")
    text = f"""# Electroactive PVDF and liquid crystal elastomer fibres for soft artificial muscles

## Introduction

Piezoelectric PVDF and liquid crystal elastomers (LCEs) are complementary materials for soft actuators. In PVDF, the β-phase content reached 89.9% in electrospun fibres compared with 78.9% in solvent-cast membranes [{n['ali']}]; hot pressing improves β-phase ordering in 3D-printed PVDF [{n['toru']}], recycled PVDF can be precipitated as high-β granules [{n['sezer']}], and rGO-reinforced PVDF-HFP composites harvest energy under hand tapping [{n['parth']}]. Silane-functionalized nanocomposites have been used to tune superabsorbent polymer matrices [{n['sujitha']}].

For LCEs, optical-fibre actuators driven by an 808 nm laser kept their maximum surface temperature above 48 °C during actuation [{n['luo']}], and cytocompatible spun LCE fibres performed mass-specific work of up to 13.2 J/kg [{n['ben26']}]. Bistable LCE metastructures switch beam direction with zero holding power [{n['yang']}], corona-poled PVDF/LCE bilayer fibres combine actuation with self-sensing [{n['fab']}], and polymorphic self-poisoning was recently described in poly(lactic acid) crystallization [{n['arxiv']}].

## References

""" + "\n\n".join(f"[{i}] {refs[k]}" for i, k in enumerate(order, start=1)) + "\n"
    r = lambda k: f"[{n[k]}]"
    items = [
        claim(r("luo"), "CLAIM_DIRECTION", [r("luo"), "Luo"], ["above 48"], "kept their maximum surface temperature above 48 °C",
              "these LCE optical fibers generate 30% contraction strain in 23 s, maintaining maximum surface temperature <48 °C",
              D["luo"]),
        claim(r("ben26"), "CLAIM_NUMBER", [r("ben26"), "Benecke"], ["13.2"], "mass-specific work of up to 13.2 J/kg",
              "an artificial muscle fiber capable of performing mass specific work of up to 31.2 J kg−1", D["ben26"]),
        claim(r("ali"), "CLAIM_OK", ["89.9"], ["89.9"], "89.9% in electrospun fibres compared with 78.9%",
              "higher β-phase content in electrospun fibers (89.9%) compared to solvent-cast membranes (78.9%)", D["ali"]),
        ok(r("parth"), [r("parth"), "Parthasarathy"], D["parth"]),
        ok(r("toru"), [r("toru"), "Toru"], D["toru"]),
        ok(r("sezer"), [r("sezer"), "Sezer"], D["sezer"]),
        ok(r("luo"), [r("luo"), "Luo"], D["luo"]),
        ok(r("ben26"), [r("ben26"), "Benecke"], D["ben26"]),
        ok(r("ali"), [r("ali"), "Ali"], D["ali"]),
        error(r("yang"), "WRONG_YEAR", [r("yang"), "Yang Y", "Y. Yang"], "Appl. Sci. 16(19) 9732 was published in 2026, not 2023.",
              "Change the year to 2026.", D["yang"], cited_year=2023, true_year=2026),
        error(r("sujitha"), "RETRACTED", [r("sujitha"), "Sujitha"], "Retracted (CrossRef updated-by: retraction).",
              "Remove it.", D["sujitha"]),
        error(r("fab"), "FAB_DOI", [r("fab"), "Ortega", "polym18091377"],
              "DOI 10.3390/polym18091377 does not exist; no such paper.", "Remove the reference and the sentence."),
        unindexed(r("arxiv"), [r("arxiv"), "2510.20370", "self-poisoning"], "https://arxiv.org/abs/2510.20370"),
    ]
    return text, None, items


# --- M6: rehabilitation pilot trials, LaTeX + BibTeX ---------------------------------------

def m6():
    D = {"yangz": "10.1186/s13018-025-06193-1", "tam": "10.1186/s12877-026-07192-5", "noda": "10.12965/jer.2550446.223",
         "ryu": "10.1097/md.0000000000050120", "suk": "10.1186/s12984-025-01716-7", "kilkki": "10.2196/78091",
         "luney": "10.1213/xaa.0000000000001891", "alor": "10.3390/healthcare13192465", "mahm": "10.3390/medicina61040602",
         "good": "10.1016/j.clgc.2025.102422"}
    keys = {"yangz": "yang2025repairs", "tam": "tamuleviciute2026", "noda": "noda2022sts", "ryu": "ryu2026robot",
            "suk": "suk2025vr", "kilkki": "kilkki2025", "luney": "luney2025", "alor": "aloraini2025", "mahm": "mahmoud2025",
            "good": "goodstein2025"}
    suk_names = swap_first_two(authors(D["suk"]))
    bib = [bibtex(keys[k], D[k]) for k in ("yangz", "tam", "ryu", "kilkki", "alor", "mahm", "good")]
    bib.append(bibtex(keys["noda"], D["noda"], yr=2022))
    bib.append(bibtex(keys["suk"], D["suk"], names=suk_names))
    bib.append(bibtex(keys["luney"], D["luney"], cite_doi="10.3390/geriatrics10040095"))
    bib.append("@article{lindgren2025,\n  author  = {Lindgren, Maria and Haddad, Rami and Oyelaran, Tunde},\n"
               "  title   = {{Home-based eccentric training after hip arthroplasty in adults over 75: a pilot randomized trial}},\n"
               "  journal = {Clinical Rehabilitation},\n  volume  = {39},\n  number  = {4},\n  pages   = {512--521},\n"
               "  year    = {2025}\n}")
    tex = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\title{Early rehabilitation after orthopaedic and cardiac surgery: what recent pilot trials show}
\author{}
\date{}
\begin{document}
\maketitle

\section{Introduction}
Pilot trials are the usual first step for rehabilitation interventions after surgery. After total joint replacement, all participants in the REPAIRS pilot received a non-opioid regimen of naproxen \SI{500}{\micro\gram} every 12 hours \cite{yang2025repairs}, and the trial recruited 53 participants, a recruitment rate of 41\% \cite{yang2025repairs}. In older adults after cardiac surgery, 100 of 336 patients screened were randomized to home exercise training or usual activity \cite{tamuleviciute2026}. Modified sit-to-stand training increased loading on the affected limb after hip fracture \cite{noda2022sts}, and home-based eccentric training after hip arthroplasty was feasible in adults over 75 \cite{lindgren2025}.

Technology-assisted approaches are spreading. In robot-assisted therapy for adhesive capsulitis, external rotation declined over time in the treatment group \cite{ryu2026robot}. Virtual-reality rehabilitation was tested for postoperative C5 palsy \cite{suk2025vr}, and technology-assisted upper-extremity training after spinal cord injury in a crossover pilot \cite{kilkki2025}.

\section{Perioperative context}
Hypotension prevention during hip fracture surgery \cite{luney2025}, outcomes of subtotal cholecystectomy techniques \cite{aloraini2025}, prosthetic joint infection after hemiarthroplasty \cite{mahmoud2025}, and upstaging after surgery for renal cell carcinoma \cite{goodstein2025} define the clinical background for these programmes.

\bibliographystyle{vancouver}
\bibliography{references}
\end{document}
"""
    items = [
        claim("yang2025repairs", "CLAIM_UNIT", ["yang2025repairs", "naproxen"], ["500 µg", "500 μg", "\\micro\\gram", "microgram"],
              "naproxen 500 µg every 12 hours", "a non-opioid regimen of naproxen 500 mg 12 hourly for 7 days", D["yangz"]),
        claim("yang2025repairs", "CLAIM_NUMBER", ["yang2025repairs", "REPAIRS"], ["41%", "41\\%"],
              "a recruitment rate of 41%", "of which 72 were eligible and 53 were recruited (recruitment rate = 21%)", D["yangz"]),
        claim("ryu2026robot", "CLAIM_DIRECTION", ["ryu2026robot", "Ryu", "adhesive capsulitis"], ["declined"],
              "external rotation declined over time in the treatment group",
              "external rotation significantly improved over time in the case group (P = .042)", D["ryu"]),
        claim("tamuleviciute2026", "CLAIM_OK", ["336"], ["336"], "100 of 336 patients screened were randomized",
              "Out of 336 assessed for eligibility, 100 patients ... were randomized", D["tam"]),
        ok("yang2025repairs", ["yang2025repairs"], D["yangz"]),
        ok("tamuleviciute2026", ["tamuleviciute2026"], D["tam"]),
        error("noda2022sts", "WRONG_YEAR", ["noda2022sts", "Noda"], "J Exerc Rehabil 21(4) 210–218 was published in 2025, not 2022.",
              "Change the year to 2025.", D["noda"], cited_year=2022, true_year=2025),
        ok("ryu2026robot", ["ryu2026robot"], D["ryu"]),
        error("suk2025vr", "WRONG_AUTHOR", ["suk2025vr"], "First author is Suk, Kyung-Soo; the entry lists Park, Jinyoung first.",
              "Put Suk, Kyung-Soo first.", D["suk"]),
        ok("kilkki2025", ["kilkki2025", "Kilkki"], D["kilkki"]),
        error("luney2025", "DOI_SWAP", ["luney2025", "Luney"],
              "The DOI 10.3390/geriatrics10040095 is Yayan & Biancosino (2025), age-related outcomes in pleural empyema; Luney et al. is "
              "10.1213/XAA.0000000000001891.", "Use 10.1213/XAA.0000000000001891.", D["luney"],
              cited_doi="10.3390/geriatrics10040095"),
        ok("aloraini2025", ["aloraini2025", "Aloraini"], D["alor"]),
        ok("mahmoud2025", ["mahmoud2025", "Mahmoud"], D["mahm"]),
        error("goodstein2025", "RETRACTED", ["goodstein2025", "Goodstein", "upstaging"], "Retracted (CrossRef updated-by: retraction).",
              "Remove it.", D["good"]),
        error("lindgren2025", "FAB_NODOI", ["lindgren2025", "Lindgren", "eccentric"], "No such paper (no CrossRef record with this title).",
              "Remove the entry and the sentence.",
              cited_title="Home-based eccentric training after hip arthroplasty in adults over 75: a pilot randomized trial"),
    ]
    return tex, "\n\n".join(bib) + "\n", items


# --- M7: Korean, ceramics and materials physics -------------------------------------------

def m7():
    order = ["kim", "kang", "seo", "kwon", "kimsy", "sekar", "qadir", "sun", "metel", "jkps", "fab", "thesis"]
    D = {"kim": "10.1007/s43207-025-00545-7", "kang": "10.1007/s43207-025-00478-1", "seo": "10.1007/s43207-025-00576-0",
         "kwon": "10.1007/s43207-025-00570-6", "kimsy": "10.1007/s43207-026-00612-7", "sekar": "10.3311/ppch.38835",
         "qadir": "10.3390/mi17050537", "sun": "10.1590/1517-7076-rmat-2024-0777", "metel": "10.3390/plasma9030026",
         "jkps": "10.1007/s40042-025-01537-w"}
    n = {k: i + 1 for i, k in enumerate(order)}
    kang_names = swap_first_two(authors(D["kang"]))
    refs = {k: apa(v) for k, v in D.items() if k != "jkps"}
    refs["kang"] = apa(D["kang"], names=kang_names)
    refs["jkps"] = physics(D["jkps"], page="625")
    refs["fab"] = ("Choi, J., Park, H., & Yoon, S. (2025). Low-temperature sintering of BaTiO3–glass composites for "
                   "flexible multilayer capacitors. *Journal of the Korean Ceramic Society*, 62(4), 801–809. "
                   "https://doi.org/10.1007/s43207-025-00671-3")
    refs["thesis"] = THESIS_NCM[0]
    text = f"""# 세라믹 및 박막 소재의 열적·자기적 특성 평가 연구 동향

## 서론

할로겐화물 페로브스카이트 기반 저항 변화 메모리 설계[{n['kim']}], TiO2/g-C3N4 촉매의 광촉매 성능 향상[{n['kang']}], 고유 트랩 상태가 전기·광전 특성에 미치는 영향[{n['seo']}], 석유화학 폐촉매에서 회수한 알루미나의 LED 형광체 재활용[{n['kwon']}], P3HT-CdSe 테트라포드 기반 습도 센서[{n['kimsy']}]가 최근 한국세라믹학회지에 보고되었다. 저온 소결 BaTiO3–유리 복합체는 유연 적층 커패시터에 쓰였다[{n['fab']}].

## 열적·자기적 특성

고에너지 볼밀링한 SiC 나노입자는 밀링 시간이 길어질수록 질량 손실이 4.24%에서 2%로 줄었다[{n['sekar']}]. Terfenol-D 격자를 쓴 유연 SAW 자기 센서는 5 mT에서 최대 377 MHz의 주파수 이동을 보였다[{n['qadir']}]. 낮은 산소 분압에서 성장한 EuTiO3 박막의 퀴리 온도는 약 41 K였다[{n['sun']}]. 중공 음극 글로우 방전으로 질소 이온을 주입하면 40 μm 두께 표면층의 경도가 13 GPa에 이른다[{n['metel']}]. 수소에 노출된 비정질 산화물의 표면 화학 상태 변화도 분석되었다[{n['jkps']}]. 니켈계 리튬 전이금속 산화물의 열분해 메커니즘은 학위논문으로 정리되었다[{n['thesis']}].

## 참고문헌

""" + "\n\n".join(f"[{i}] {refs[k]}" for i, k in enumerate(order, start=1)) + "\n"
    r = lambda k: f"[{n[k]}]"
    items = [
        claim(r("sekar"), "CLAIM_DIRECTION", [r("sekar"), "Sekar", "SiC"], ["4.24%에서 2%", "줄었다"],
              "밀링 시간이 길어질수록 질량 손실이 4.24%에서 2%로 줄었다",
              "Milling for a longer time caused mass loss to increase, ranging from 2% to 4.24%", D["sekar"]),
        claim(r("qadir"), "CLAIM_UNIT", [r("qadir"), "Qadir", "SAW"], ["377 MHz"], "5 mT에서 최대 377 MHz의 주파수 이동",
              "a maximum frequency shift of 377 kHz at 5 mT", D["qadir"]),
        claim(r("sun"), "CLAIM_NUMBER", [r("sun"), "Sun", "EuTiO3"], ["41 K"], "퀴리 온도는 약 41 K",
              "Films grown under low oxygen pressure exhibit a peak in the Curie temperature (Tc) around 4.1 K", D["sun"]),
        claim(r("metel"), "CLAIM_OK", ["13 GPa"], ["13 GPa"], "40 μm 두께 표면층의 경도가 13 GPa",
              "production of a 40 µm thick surface layer with hardness of 13 GPa", D["metel"]),
        ok(r("kim"), [r("kim"), "Kim, H."], D["kim"]),
        error(r("kang"), "WRONG_AUTHOR", [r("kang"), "Xu, Q", "Kang"], "First author is Kang, H.-S.; the reference lists Xu, Q. first.",
              "Put Kang, H.-S. first.", D["kang"]),
        ok(r("seo"), [r("seo"), "Seo"], D["seo"]),
        ok(r("kwon"), [r("kwon"), "Kwon"], D["kwon"]),
        ok(r("kimsy"), [r("kimsy"), "Kim, S.-Y.", "P3HT"], D["kimsy"]),
        ok(r("sekar"), [r("sekar"), "Sekar"], D["sekar"]),
        ok(r("qadir"), [r("qadir"), "Qadir"], D["qadir"]),
        ok(r("sun"), [r("sun"), "Sun, G."], D["sun"]),
        ok(r("metel"), [r("metel"), "Metel"], D["metel"]),
        error(r("jkps"), "TITLELESS_WRONG_VOLPAGE", [r("jkps"), "Kang", "88, 625"],
              "S. J. Kang et al., J. Korean Phys. Soc. 88 starts on page 652, not 625 (doi:10.1007/s40042-025-01537-w).",
              "Change the page to 652.", D["jkps"], cited_volume="88", cited_page="625"),
        error(r("fab"), "FAB_DOI", [r("fab"), "Choi, J.", "00671-3", "BaTiO3–glass"],
              "DOI 10.1007/s43207-025-00671-3 does not exist; no such paper.", "Remove the reference and the sentence."),
        unindexed(r("thesis"), [r("thesis"), "박성민"], THESIS_NCM[1]),
    ]
    return text, None, items


# --- M8: thin-film magnetism and plasma physics, English, physics style -----------------------

def m8():
    order = ["gali", "ichi", "han", "sara", "navr", "zhou", "huang", "hwang", "park", "alwany", "fab", "arxiv"]
    D = {"gali": "10.1088/1361-6463/add7e9", "ichi": "10.1063/5.0326956", "han": "10.3390/ma19143012",
         "sara": "10.3390/nano16090558", "navr": "10.1088/1361-6595/adaa9b", "zhou": "10.1088/1361-6595/ae5d6a",
         "huang": "10.3390/plasma9030036", "hwang": "10.1007/s40042-026-01566-z", "park": "10.1007/s40042-026-01570-3",
         "alwany": "10.1007/s10904-024-03325-8"}
    n = {k: i + 1 for i, k in enumerate(order)}
    refs = {k: physics(v) for k, v in D.items()}
    refs["navr"] = physics(D["navr"], volume="35")
    refs["hwang"] = physics(D["hwang"], page="1072")
    refs["fab"] = ('R. Castellanos and T. Ivanova, "Voltage-gated skyrmion nucleation in ultrathin CoFeB/Pd multilayers," '
                   "Phys. Rev. Appl. 23, 044051 (2025).")
    refs["arxiv"] = arxiv_ref("2609.05383", "physics")
    text = f"""# Interface-controlled magnetism and plasma diagnostics for spintronic thin films

## Introduction

Perpendicular magnetic anisotropy (PMA) in thin films can be tuned by thickness, annealing, and electric fields. In Ta/GdFeCo/Ta heterostructures, PMA dominates near room temperature only in films thinner than 90 nm [{n['gali']}]. CoFe/Fe stacks deposited at 100 K reached a voltage-controlled magnetic anisotropy coefficient of 61 fJ/Vm after annealing at 673 K [{n['ichi']}], and lithium-ion migration in TiO2/CoNi suppressed the remanence and coercivity to zero within a voltage window of 1.5 kV [{n['han']}]. Annealed [CoFeB/Pd]×5 multilayers reached an effective anisotropy of about 7.82 × 10⁵ erg/cc [{n['sara']}], spin spirals can be customized in ferromagnetic films [{n['arxiv']}], and voltage-gated skyrmion nucleation has been reported in CoFeB/Pd multilayers [{n['fab']}]. Film-thickness effects on optical constants have also been analysed for Ge–Se–Zn chalcogenide films [{n['alwany']}].

## Deposition plasma diagnostics

Plasma diagnostics use Ar I line-intensity ratios for electric-field measurement [{n['navr']}], metastable-neutral measurements [{n['zhou']}], and electron temperature measurements in dielectric barrier discharges [{n['huang']}]. Beamline characterization with coherent X-rays [{n['hwang']}] and polarization-dependent X-ray absorption [{n['park']}] complete the toolset.

## References

""" + "\n\n".join(f"[{i}] {refs[k]}" for i, k in enumerate(order, start=1)) + "\n"
    r = lambda k: f"[{n[k]}]"
    items = [
        claim(r("gali"), "CLAIM_DIRECTION", [r("gali"), "Galivarapu", "GdFeCo"], ["thinner than 90"],
              "PMA dominates near room temperature only in films thinner than 90 nm",
              "PMA begins to dominate at around room temperature for films with a thickness greater than 90 nm", D["gali"]),
        claim(r("ichi"), "CLAIM_NUMBER", [r("ichi"), "Ichinose", "CoFe/Fe"], ["61 fJ"],
              "a voltage-controlled magnetic anisotropy coefficient of 61 fJ/Vm",
              "a voltage-controlled magnetic anisotropy coefficient of 161 fJ/Vm even after annealing at 673 K", D["ichi"]),
        claim(r("han"), "CLAIM_UNIT", [r("han"), "Han", "CoNi"], ["1.5 kV"], "within a voltage window of 1.5 kV",
              "Within a voltage window of 1.5 V (from 3.0 V to 1.5 V), both remanent magnetization and coercivity are suppressed to zero",
              D["han"]),
        # The CrossRef abstract prints 10^5 as "105" (superscript lost); the quote keeps its text.
        claim(r("sara"), "CLAIM_OK", ["7.82"], ["7.82"], "an effective anisotropy of about 7.82 × 10⁵ erg/cc",
              "A maximum effective PMA energy density (Keff) of ≈7.82 × 105 erg/cc", D["sara"]),
        ok(r("gali"), [r("gali"), "Galivarapu"], D["gali"]),
        ok(r("ichi"), [r("ichi"), "Ichinose"], D["ichi"]),
        ok(r("han"), [r("han"), "Han"], D["han"]),
        ok(r("sara"), [r("sara"), "Saravanan"], D["sara"]),
        error(r("navr"), "TITLELESS_WRONG_VOLPAGE", [r("navr"), "Navrátil", "Navratil"],
              "Navrátil et al., Plasma Sources Sci. Technol. 015013 is in volume 34 (2025), not 35 (doi:10.1088/1361-6595/adaa9b).",
              "Change the volume to 34.", D["navr"], cited_volume="35", cited_page="015013"),
        ok(r("zhou"), [r("zhou"), "Zhou"], D["zhou"]),
        ok(r("huang"), [r("huang"), "Huang"], D["huang"]),
        error(r("hwang"), "TITLELESS_WRONG_VOLPAGE", [r("hwang"), "Hwang", "1072"],
              "Hwang et al., J. Korean Phys. Soc. 88 starts on page 1027, not 1072 (doi:10.1007/s40042-026-01566-z).",
              "Change the page to 1027.", D["hwang"], cited_volume="88", cited_page="1072"),
        ok(r("park"), [r("park"), "Park"], D["park"]),
        error(r("alwany"), "RETRACTED", [r("alwany"), "Alwany"], "Retracted (CrossRef updated-by: retraction).",
              "Remove it.", D["alwany"]),
        error(r("fab"), "FAB_NODOI", [r("fab"), "Castellanos", "skyrmion"], "No such paper (no CrossRef record with this title).",
              "Remove the reference and the sentence.",
              cited_title="Voltage-gated skyrmion nucleation in ultrathin CoFeB/Pd multilayers"),
        unindexed(r("arxiv"), [r("arxiv"), "2609.05383", "Panchwanee"], "https://arxiv.org/abs/2609.05383"),
    ]
    return text, None, items


MANUSCRIPTS = {
    "v2m1_dea_en": (m1, "md", "en", "materials / dielectric elastomers", "markdown (APA, author-date)"),
    "v2m2_ionic_en": (m2, "md", "en", "materials / ionic polymer actuators", "markdown (Vancouver)"),
    "v2m3_crystal_latex": (m3, "latex", "en", "materials / thermal analysis and crystallization", "LaTeX + BibTeX"),
    "v2m4_polymer_ko": (m4, "md", "ko", "materials / Korean polymer journals", "markdown (Korean, numbered)"),
    "v2m5_pvdf_lce_en": (m5, "md", "en", "materials / PVDF and liquid crystal elastomers", "markdown (IEEE)"),
    "v2m6_rehab_latex": (m6, "latex", "en", "biomedicine / rehabilitation pilot trials", "LaTeX + BibTeX"),
    "v2m7_ceramic_ko": (m7, "md", "ko", "materials / ceramics and thin films", "markdown (Korean, numbered)"),
    "v2m8_magnetism_en": (m8, "md", "en", "physics / thin-film magnetism and plasma", "markdown (physics style, no titles)"),
}
ERROR_TYPES = ("FAB_DOI", "FAB_NODOI", "DOI_SWAP", "RETRACTED", "WRONG_YEAR", "WRONG_AUTHOR", "TITLELESS_WRONG_VOLPAGE",
               "CLAIM_NUMBER", "CLAIM_UNIT", "CLAIM_DIRECTION")


def main() -> None:
    out_dir = HERE / "manuscripts"
    out_dir.mkdir(exist_ok=True)
    manuscripts = {}
    counts: dict[str, int] = {}
    for name, (builder, kind, language, domain, style) in MANUSCRIPTS.items():
        text, bib, items = builder()
        entry = {"language": language, "domain": domain, "format": style}
        if kind == "latex":
            folder = out_dir / name
            folder.mkdir(exist_ok=True)
            (folder / "main.tex").write_text(text, encoding="utf-8")
            (folder / "references.bib").write_text(bib, encoding="utf-8")
            entry["path"] = f"manuscripts/{name}/main.tex"
            entry["bib"] = f"manuscripts/{name}/references.bib"
        else:
            (out_dir / f"{name}.md").write_text(text, encoding="utf-8")
            entry["path"] = f"manuscripts/{name}.md"
        for index, item in enumerate(items, start=1):
            item["id"] = f"{name}#{index:02d}"
            if item["type"] == "WRONG_AUTHOR":
                # Every WRONG_AUTHOR item swaps the first two authors.
                names = authors(item["truth_doi"])
                item["true_first_author"], item["cited_first_author"] = names[0][0], names[1][0]
            if item["type"] == "TITLELESS_WRONG_VOLPAGE":
                item["true_volume"], item["true_page"] = src(item["truth_doi"])["volume"], first_page(item["truth_doi"])
            item["expected"] = "FLAG" if item["type"] in ERROR_TYPES else "NOT_FLAG"
            counts[item["type"]] = counts.get(item["type"], 0) + 1
        entry["items"] = items
        manuscripts[name] = entry
    cited = [i.get("cited_by") for m in manuscripts.values() for i in m["items"] if i.get("cited_by") is not None]
    payload = {
        "description": "v2: planted errors and correct references in manuscripts built only from obscure papers; see README.md.",
        "selection_rule": "real cited papers: 2025-2026 (two retracted papers 2023-2024), CrossRef is-referenced-by-count <= 30, "
        "not recognised by the set's author before fetching; plus arXiv preprints and Korean theses that CrossRef lacks",
        "fetched": FETCHED,
        "max_cited_by": max(cited),
        "error_types": list(ERROR_TYPES),
        "counts": counts,
        "manuscripts": manuscripts,
    }
    (HERE / "truth.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=1), "max cited_by:", max(cited))


if __name__ == "__main__":
    main()
