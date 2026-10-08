// Korean wording for the reasons check-bib writes (src/ref_verify/reference_resolve.py,
// doi_check.py, crossref.py). The engine output stays English; only the page translates.
// In `en`, {name} matches any text and is copied into `ko` unchanged, and {name:list}
// is translated item by item with LISTS[list]. tests/test_web_reasons.py fails when the
// engine gains a reason phrase that no `en` template here contains.

const REASONS = [
  {
    en: "Provided citation metadata matches the fetched CrossRef record.",
    ko: "적힌 서지 정보가 CrossRef 기록과 일치합니다.",
  },
  {
    en: "Insufficient citation metadata was provided to verify the fetched CrossRef record.",
    ko: "CrossRef 기록과 비교할 서지 정보가 부족합니다.",
  },
  {
    en: "DOI resolves, but minor metadata differs from the provided citation.",
    ko: "DOI는 맞지만 서지 정보 일부가 조금 다릅니다.",
  },
  {
    en: "DOI resolves to a materially different paper than provided.",
    ko: "DOI가 가리키는 논문이 적힌 것과 상당히 다릅니다.",
  },
  {
    en: "DOI resolves to a materially different paper than provided: {details:diffs}.",
    ko: "DOI가 가리키는 논문이 적힌 것과 상당히 다릅니다: {details}.",
  },
  {
    en: "DOI matches, but {details:diffs}.",
    ko: "DOI는 맞지만 다른 부분이 있습니다: {details}.",
  },
  {
    en: "DOI resolves, but the reference does not carry enough matching title and first-author text to confirm it is this paper; verify this reference manually.",
    ko: "DOI는 있지만, 이 논문이 맞다고 확인할 만큼 제목과 제1저자가 참고문헌에 적혀 있지 않습니다. 직접 확인하세요.",
  },
  {
    en: "The DOI and title match CrossRef, but its first author ({author}) was not found in the reference's first-author position; check the author names manually.",
    ko: "DOI와 제목은 CrossRef와 맞지만, CrossRef의 제1저자({author})가 참고문헌의 제1저자 자리에 없습니다. 저자 이름을 직접 확인하세요.",
  },
  {
    en: "The DOI and first author match CrossRef, but its title (\"{title}\") was not found in the reference; check the title manually.",
    ko: "DOI와 제1저자는 CrossRef와 맞지만, CrossRef의 제목(\"{title}\")이 참고문헌에 없습니다. 제목을 직접 확인하세요.",
  },
  {
    en: "This DOI belongs to {paper}, which this reference does not mention; the DOI may point to a different paper.",
    ko: "이 DOI는 {paper}의 DOI인데, 참고문헌에는 이 논문이 나오지 않습니다. DOI가 다른 논문을 가리키는 것일 수 있습니다.",
  },
  {
    en: "The reference has no article title; it matches CrossRef's record for this DOI on {fields:fields}.",
    ko: "참고문헌에 논문 제목은 없지만, {fields}가 이 DOI의 CrossRef 기록과 일치합니다.",
  },
  {
    en: "The reference has no article title, and CrossRef's record for this DOI differs in {details:titleless}.",
    ko: "참고문헌에 논문 제목이 없고, 이 DOI의 CrossRef 기록과 다른 항목이 있습니다: {details}.",
  },
  {
    en: "CrossRef records this paper as retracted (notice DOI {doi}); do not use it as a source.",
    ko: "CrossRef에 철회된 논문으로 기록되어 있습니다(철회 공지 DOI {doi}). 출처로 쓰지 마세요.",
  },
  {
    en: "CrossRef has no record for this DOI (HTTP 404), and doi.org does not list it either.",
    ko: "CrossRef에 이 DOI 기록이 없고(HTTP 404), doi.org에도 없습니다.",
  },
  {
    en: "This DOI is registered with {agency}, not CrossRef, so its title and authors were not compared; open https://doi.org/{doi} to confirm it is this work.",
    ko: "이 DOI는 CrossRef가 아니라 {agency}에 등록되어 있어 제목과 저자를 비교하지 않았습니다. https://doi.org/{doi} 를 열어 이 논문이 맞는지 확인하세요.",
  },
  {
    en: "Matched CrossRef record {doi} by bibliographic search; the reference has no article title, so it was matched on {fields:fields}.",
    ko: "서지 검색으로 CrossRef 기록({doi})을 찾았습니다. 참고문헌에 논문 제목이 없어 {fields}로 맞춰 보았습니다.",
  },
  {
    en: "Matched CrossRef record {doi} by bibliographic search, but {details:diffs}.",
    ko: "서지 검색으로 CrossRef 기록({doi})을 찾았지만 다른 부분이 있습니다: {details}.",
  },
  {
    en: "Matched CrossRef record {doi} by bibliographic search.",
    ko: "서지 검색으로 CrossRef 기록({doi})을 찾았습니다.",
  },
  {
    en: "No matching CrossRef record was found; verify this reference manually.",
    ko: "CrossRef에서 맞는 기록을 찾지 못했습니다. 직접 확인하세요.",
  },
  {
    // The browser keeps no cache, so the CLI's "already checked are cached" is left out.
    en: "Not checked: CrossRef asked ref-verify to slow down (HTTP 429). Run the same command again in a minute; references already checked are cached.",
    ko: "확인하지 못했습니다. CrossRef가 요청 속도를 줄여 달라고 했습니다(HTTP 429). 1분 뒤 다시 검사하세요.",
  },
  {
    en: "Not checked: could not reach CrossRef ({error}). Check the internet connection and run again.",
    ko: "확인하지 못했습니다. CrossRef에 연결할 수 없습니다({error}). 인터넷 연결을 확인하고 다시 검사하세요.",
  },
  {
    en: "Reference could not be checked: {error}",
    ko: "이 참고문헌은 확인하지 못했습니다: {error}",
  },
];

const LISTS = {
  // reference_resolve._differences, joined with " and ".
  diffs: {
    separator: " and ",
    joiner: ", ",
    items: [
      { en: "the title differs (CrossRef: \"{title}\")", ko: "제목 다름(CrossRef: \"{title}\")" },
      {
        en: "the first author differs (reference: {reference}; CrossRef: {crossref})",
        ko: "제1저자 다름(참고문헌: {reference}, CrossRef: {crossref})",
      },
      { en: "the first author differs (CrossRef: {crossref})", ko: "제1저자 다름(CrossRef: {crossref})" },
      {
        en: "the year differs (reference: {reference}; CrossRef: {crossref})",
        ko: "연도 다름(참고문헌: {reference}, CrossRef: {crossref})",
      },
      { en: "the year differs (CrossRef: {crossref})", ko: "연도 다름(CrossRef: {crossref})" },
    ],
  },
  // reference_resolve._titleless_differences, joined with "; ".
  titleless: {
    separator: "; ",
    joiner: ", ",
    items: [
      { en: "journal (CrossRef: {value})", ko: "학술지(CrossRef: {value})" },
      { en: "volume (CrossRef: {value})", ko: "권(CrossRef: {value})" },
      { en: "first page (CrossRef: {value})", ko: "첫 페이지(CrossRef: {value})" },
      { en: "year (reference: {reference}; CrossRef: {crossref})", ko: "연도(참고문헌: {reference}, CrossRef: {crossref})" },
      { en: "year (CrossRef: {crossref})", ko: "연도(CrossRef: {crossref})" },
      { en: "first author (CrossRef: {value})", ko: "제1저자(CrossRef: {value})" },
    ],
  },
};

// reference_resolve._titleless_fields: "journal, volume, first page, year, and first author".
const FIELDS = { journal: "학술지", volume: "권", "first page": "첫 페이지", year: "연도", "first author": "제1저자" };
// A value the engine writes when CrossRef lists nothing.
const VALUES = { "none listed": "기록 없음" };

function compile(template) {
  const names = [];
  const pattern = template.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\\\{(\w+)(?::(\w+))?\\\}/g, (_, name, list) => {
    names.push({ name, list });
    return "(.+?)";
  });
  return { regex: new RegExp(`^${pattern}$`, "s"), names };
}

function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, (_, name) => values[name]);
}

function translateWith(text, entries, lists) {
  for (const entry of entries) {
    entry.compiled ??= compile(entry.en);
    const match = entry.compiled.regex.exec(text);
    if (!match) continue;
    const values = {};
    let ok = true;
    entry.compiled.names.forEach(({ name, list }, index) => {
      const captured = match[index + 1];
      if (!list) {
        values[name] = VALUES[captured] ?? captured;
        return;
      }
      const translated = list === "fields" ? translateFields(captured) : translateList(captured, lists[list]);
      if (translated === null) ok = false;
      values[name] = translated;
    });
    if (ok) return fill(entry.ko, values);
  }
  return null;
}

function translateList(text, list) {
  // Split before matching the whole text, or one item's value would swallow the items after
  // it. Every separator position is tried, since titles and values can contain it too.
  for (let at = text.indexOf(list.separator); at !== -1; at = text.indexOf(list.separator, at + 1)) {
    const head = translateWith(text.slice(0, at), list.items, {});
    if (head === null) continue;
    const tail = translateList(text.slice(at + list.separator.length), list);
    if (tail !== null) return head + list.joiner + tail;
  }
  return translateWith(text, list.items, {});
}

function translateFields(text) {
  const names = text.replace(", and ", ", ").split(", ");
  if (!names.every((name) => name in FIELDS)) return null;
  return names.map((name) => FIELDS[name]).join("·");
}

// Returns the Korean reason, or null when the engine wrote something this table lacks.
export function translateReason(text) {
  return translateWith(text, REASONS, LISTS);
}
