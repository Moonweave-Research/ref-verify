const TEXT = {
  en: {
    skip: "Skip to content",
    title: "Check every reference in your list",
    lede: "Paste a reference list or choose a .bib, .ris, or .txt file. Each reference is compared with its CrossRef record: title, first author, and year.",
    pasteLabel: "Reference list",
    pasteHint: "One reference per line or numbered item. BibTeX and RIS can be pasted too.",
    pastePlaceholder: "[1] R. Pelrine, R. Kornbluh, Q. Pei, J. Joseph, High-speed electrically actuated elastomers with strain greater than 100%, Science 287 (2000) 836–839.",
    or: "or",
    chooseFile: "Choose a file",
    removeFile: "Remove",
    fileInUse: "This file is checked instead of the box above.",
    reading: "Reading the list…",
    start: "Check references",
    stop: "Stop",
    privacy: "Your references go from this browser straight to CrossRef and doi.org. There is no ref-verify server: nothing is uploaded to us or stored, and there are no analytics. The checker itself is downloaded from the jsDelivr CDN.",
    resultsTitle: "Results",
    download: "Download report (HTML)",
    calloutLead: "UNVERIFIED ≠ wrong.",
    callout: "It means the tool could not confirm the reference automatically. Look it up once yourself.",
    reasonsNote: "Reasons are written by the checker in English.",
    footCli: "Prefer the terminal? The same checker runs as",
    loading: "Loading the checker…",
    loadingNote: "The first visit downloads about 6 MB (a Python runtime). After that the browser keeps it, and loading takes a second or two.",
    starting: (total) => `Checking ${total} references…`,
    progress: (done, total) => `Checked ${done} of ${total}`,
    remaining: (seconds) => (seconds < 60 ? `About ${seconds} s left.` : `About ${Math.round(seconds / 60)} min left.`),
    pacing: "CrossRef answers about one search per second, so each reference takes a second or two.",
    stopped: "Stopped. Nothing was kept; you can start again.",
    errEmpty: "Paste a reference list or choose a file.",
    errDocument: "Word, PDF, and HWP files can't be read directly. Copy the reference list and paste it in the box.",
    errFormat: "Choose a .bib, .ris, .txt, or .md file, or paste the list in the box.",
    errInput: "The reference list could not be read.",
    errLoad: "The checker could not be downloaded. Check the internet connection and reload the page.",
    errRun: "Something went wrong while checking.",
    total: "total",
    notChecked: "not checked, rerun",
    needsLook: (n) => `Needs a look (${n})`,
    passed: (n) => `Passed (${n})`,
    allPassed: "Nothing to fix: every reference passed.",
    headStatus: "Status",
    headReference: "Reference",
    headDoi: "DOI",
    headReason: "Reason",
    headEvidence: "Evidence",
    resolved: "found by search",
    version: (v) => `ref-verify ${v}`,
    legend: {
      PASS: "Title, first author, and year match the CrossRef record for the DOI (or the record found by search).",
      WARN: "Found, but something differs; the reason says what. Compare that reference with the source.",
      REJECT: "The DOI exists nowhere, belongs to a different paper, or the paper is retracted. Fix or remove the citation.",
      UNVERIFIED: "Could not be confirmed automatically (theses, local conference abstracts, DOIs registered outside CrossRef). This does not mean it is wrong; look it up once yourself.",
    },
  },
  ko: {
    skip: "본문으로 건너뛰기",
    title: "참고문헌이 실제 논문과 맞는지 확인하세요",
    lede: "참고문헌 목록을 붙여넣거나 .bib, .ris, .txt 파일을 고르세요. 항목마다 CrossRef 기록과 제목·제1저자·연도를 비교합니다.",
    pasteLabel: "참고문헌 목록",
    pasteHint: "한 줄에 하나, 또는 번호 붙은 항목 하나씩. BibTeX·RIS도 그대로 붙여넣을 수 있습니다.",
    pastePlaceholder: "[1] 윤혜리, 이종휘, “리포익산을 함유한 PNIPAM 하이드로젤의 제조”, 폴리머, 36권, 4호, pp. 455–460, 2012. https://doi.org/10.7317/pk.2012.36.4.455",
    or: "또는",
    chooseFile: "파일 고르기",
    removeFile: "빼기",
    fileInUse: "위 칸 대신 이 파일을 검사합니다.",
    reading: "목록을 읽는 중…",
    start: "검사 시작",
    stop: "중지",
    privacy: "참고문헌은 이 브라우저에서 CrossRef와 doi.org로만 바로 전송됩니다. ref-verify 서버는 없습니다. 저희에게 올라오거나 저장되는 것은 없고, 방문 분석 도구도 없습니다. 검사 프로그램은 jsDelivr CDN에서 내려받습니다.",
    resultsTitle: "결과",
    download: "보고서 내려받기 (HTML)",
    calloutLead: "UNVERIFIED는 ‘틀림’이 아닙니다.",
    callout: "자동으로 확인하지 못했다는 뜻입니다. 한 번 직접 찾아보세요.",
    reasonsNote: "사유는 검사 프로그램이 영어로 적습니다.",
    footCli: "터미널이 편하다면 같은 검사기를 이렇게 설치할 수 있습니다:",
    loading: "검사 프로그램을 불러오는 중…",
    loadingNote: "처음 한 번은 약 6 MB(파이썬 실행 환경)를 내려받습니다. 그다음부터는 브라우저에 남아 있어 1~2초면 됩니다.",
    starting: (total) => `참고문헌 ${total}개 검사 중…`,
    progress: (done, total) => `${total}개 중 ${done}개 확인`,
    remaining: (seconds) => (seconds < 60 ? `약 ${seconds}초 남음.` : `약 ${Math.round(seconds / 60)}분 남음.`),
    pacing: "CrossRef는 검색을 1초에 한 번 정도만 받기 때문에 항목 하나에 1~2초 걸립니다.",
    stopped: "중지했습니다. 남은 것은 없으며 다시 시작할 수 있습니다.",
    errEmpty: "참고문헌을 붙여넣거나 파일을 고르세요.",
    errDocument: "Word, PDF, HWP 파일은 바로 읽을 수 없습니다. 참고문헌 부분을 복사해 위 칸에 붙여넣으세요.",
    errFormat: ".bib, .ris, .txt, .md 파일을 고르거나 목록을 위 칸에 붙여넣으세요.",
    errInput: "참고문헌 목록을 읽지 못했습니다.",
    errLoad: "검사 프로그램을 내려받지 못했습니다. 인터넷 연결을 확인하고 페이지를 새로 고치세요.",
    errRun: "검사 중 문제가 생겼습니다.",
    total: "전체",
    notChecked: "확인 못 함, 다시 실행",
    needsLook: (n) => `확인 필요 (${n})`,
    passed: (n) => `통과 (${n})`,
    allPassed: "고칠 것이 없습니다. 모든 참고문헌이 통과했습니다.",
    headStatus: "판정",
    headReference: "참고문헌",
    headDoi: "DOI",
    headReason: "사유",
    headEvidence: "근거",
    resolved: "검색으로 찾음",
    version: (v) => `ref-verify ${v}`,
    legend: {
      PASS: "제목·제1저자·연도가 DOI(또는 검색으로 찾은 기록)의 CrossRef 기록과 일치합니다.",
      WARN: "찾았지만 다른 부분이 있습니다. 사유를 보고 원문과 비교하세요.",
      REJECT: "DOI가 존재하지 않거나, 다른 논문의 DOI이거나, 철회된 논문입니다. 고치거나 빼세요.",
      UNVERIFIED: "자동으로 확인하지 못했습니다(학위논문, 국내 학회 초록, CrossRef 밖에 등록된 DOI 등). 틀렸다는 뜻이 아닙니다. 한 번 직접 찾아보세요.",
    },
  },
};

const LABELS = ["PASS", "WARN", "REJECT", "UNVERIFIED"];
const TONES = { PASS: "pass", WARN: "warn", REJECT: "reject", UNVERIFIED: "unverified" };
const DOCUMENT_SUFFIXES = [".doc", ".docx", ".hwp", ".hwpx", ".odt", ".pages", ".pdf", ".rtf"];
const TEXT_SUFFIXES = [".bib", ".bibtex", ".ris", ".txt", ".md", ".markdown"];

const $ = (id) => document.getElementById(id);
const els = {
  form: $("form"), refs: $("refs"), file: $("file"), fileChip: $("file-chip"), fileName: $("file-name"),
  fileClear: $("file-clear"), fileNote: $("file-note"), start: $("start"), stop: $("stop"), formError: $("form-error"),
  status: $("status"), statusText: $("status-text"), statusBar: $("status-bar"), statusNote: $("status-note"),
  results: $("results"), resultsTitle: $("results-title"), counts: $("counts"), legend: $("legend"),
  tables: $("tables"), download: $("download"), engineVersion: $("engine-version"),
};

let lang = initialLanguage();
let worker = null;
let engineReady = false;
let engineVersion = null;
let running = false;
let lastResult = null;
let lastStatus = null;

function initialLanguage() {
  try {
    const saved = localStorage.getItem("ref-verify-lang");
    if (saved === "ko" || saved === "en") return saved;
  } catch {
    // Storage can be blocked; fall back to the browser language.
  }
  return (navigator.language || "en").toLowerCase().startsWith("ko") ? "ko" : "en";
}

function t(key, ...args) {
  const value = TEXT[lang][key];
  return typeof value === "function" ? value(...args) : value;
}

function applyLanguage() {
  document.documentElement.lang = lang;
  document.title = lang === "ko" ? "ref-verify: 참고문헌 검사" : "ref-verify: check references";
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  }
  for (const button of document.querySelectorAll(".lang button")) {
    button.setAttribute("aria-pressed", String(button.dataset.lang === lang));
  }
  els.engineVersion.textContent = engineVersion ? t("version", engineVersion) : "";
  if (lastStatus) showStatus(lastStatus);
  if (lastResult) renderResult(lastResult);
}

function startWorker() {
  if (worker) return;
  worker = new Worker("worker.js", { type: "module" });
  worker.onmessage = onWorkerMessage;
  worker.onerror = (event) => {
    event.preventDefault();
    failLoad(event.message || "worker error");
  };
}

function onWorkerMessage({ data }) {
  if (data.type === "ready") {
    engineReady = true;
    engineVersion = data.version;
    els.engineVersion.textContent = t("version", engineVersion);
    if (running) showStatus({ kind: "starting" });
  } else if (data.type === "load-error") {
    failLoad(data.message);
  } else if (data.type === "progress") {
    showStatus({ kind: "progress", done: data.done, total: data.total, ms: data.ms });
  } else if (data.type === "done") {
    finishRun();
    if (data.result.error) {
      showError(t("errInput"), data.result.error);
      return;
    }
    lastResult = data.result;
    renderResult(lastResult);
    els.results.hidden = false;
    els.resultsTitle.focus();
  } else if (data.type === "run-error") {
    finishRun();
    showError(t("errRun"), data.message);
  }
}

function failLoad(message) {
  worker?.terminate();
  worker = null;
  engineReady = false;
  if (running) finishRun();
  showError(t("errLoad"), message);
}

function showStatus(status) {
  lastStatus = status;
  els.status.hidden = false;
  let text = "";
  let note = "";
  if (status.kind === "loading") {
    text = t("loading");
    note = t("loadingNote");
    els.statusBar.removeAttribute("value");
  } else if (status.kind === "starting") {
    text = t("reading");
    note = t("pacing");
    els.statusBar.removeAttribute("value");
  } else if (status.kind === "progress") {
    els.statusBar.max = Math.max(status.total, 1);
    els.statusBar.value = status.done;
    if (status.done === 0) {
      text = t("starting", status.total);
      note = t("pacing");
    } else {
      text = t("progress", status.done, status.total);
      const left = Math.ceil(((status.ms / status.done) * (status.total - status.done)) / 1000);
      note = status.done < status.total ? t("remaining", Math.max(left, 1)) : "";
    }
  } else if (status.kind === "stopped") {
    text = t("stopped");
    els.statusBar.value = 0;
  }
  els.statusText.textContent = text;
  els.statusNote.textContent = note;
  els.statusBar.hidden = status.kind === "stopped";
}

function hideStatus() {
  lastStatus = null;
  els.status.hidden = true;
}

function showError(lead, detail) {
  hideStatus();
  els.formError.textContent = detail ? `${lead} (${detail})` : lead;
  els.formError.hidden = false;
}

function clearError() {
  els.formError.textContent = "";
  els.formError.hidden = true;
}

function setRunning(value) {
  running = value;
  els.start.disabled = value;
  els.refs.disabled = value;
  els.file.disabled = value;
  els.fileClear.disabled = value;
  els.stop.hidden = !value;
}

function finishRun() {
  setRunning(false);
  hideStatus();
}

function suffixOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

function pastedName(text) {
  // The engine reads the format from the file name, so name pasted text by its content.
  const head = text.trimStart();
  if (head.startsWith("@")) return "pasted.bib";
  if (/^TY {2}- /m.test(head)) return "pasted.ris";
  return "pasted.txt";
}

async function onSubmit(event) {
  event.preventDefault();
  if (running) return;
  clearError();
  const file = els.file.files[0];
  let name;
  let bytes;
  if (file) {
    const suffix = suffixOf(file.name);
    if (DOCUMENT_SUFFIXES.includes(suffix)) return showError(t("errDocument"));
    if (!TEXT_SUFFIXES.includes(suffix)) return showError(t("errFormat"));
    name = file.name;
    bytes = new Uint8Array(await file.arrayBuffer());
  } else {
    const text = els.refs.value;
    if (!text.trim()) {
      showError(t("errEmpty"));
      els.refs.focus();
      return;
    }
    name = pastedName(text);
    bytes = new TextEncoder().encode(text);
  }
  lastResult = null;
  els.results.hidden = true;
  setRunning(true);
  startWorker();
  showStatus({ kind: engineReady ? "starting" : "loading" });
  worker.postMessage({ name, bytes }, [bytes.buffer]);
}

function onStop() {
  // The engine runs synchronously inside the worker, so stopping means ending the worker.
  worker?.terminate();
  worker = null;
  engineReady = false;
  setRunning(false);
  showStatus({ kind: "stopped" });
  startWorker();
}

function onFileChange() {
  const file = els.file.files[0];
  clearError();
  els.fileChip.hidden = !file;
  els.fileName.textContent = file ? file.name : "";
  els.refs.disabled = Boolean(file);
  els.fileNote.hidden = !file;
  if (file) startWorker();
}

function clearFile() {
  els.file.value = "";
  onFileChange();
  els.refs.focus();
}

function doiHref(doi) {
  return doi && doi.startsWith("10.") ? "https://doi.org/" + encodeURIComponent(doi).replace(/%2F/gi, "/") : null;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

function badge(label) {
  return el("span", { class: `badge ${TONES[label] || "warn"}` }, label);
}

function renderResult(result) {
  const rows = result.rows;
  const summary = result.payload.summary;
  // Counted by the label shown, like the report, so the boxes add up to the total.
  const counts = [["total", t("total"), rows.length, ""]];
  for (const label of LABELS) {
    counts.push([label, label, rows.filter((row) => row.label === label).length, TONES[label]]);
  }
  if (summary.failed) counts.push(["failed", t("notChecked"), summary.failed, "warn"]);
  els.counts.replaceChildren(
    ...counts.map(([, name, value, tone]) =>
      el("div", { class: `count ${tone}` }, el("span", { class: "n" }, String(value)), el("span", { class: "label" }, name)),
    ),
  );
  els.legend.replaceChildren(...LABELS.map((label) => el("li", {}, badge(label), " ", TEXT[lang].legend[label])));

  const flagged = rows.filter((row) => row.tone !== "pass");
  const passed = rows.filter((row) => row.tone === "pass");
  const parts = [el("h3", {}, t("needsLook", flagged.length))];
  parts.push(flagged.length ? table(flagged) : el("p", { class: "empty" }, t("allPassed")));
  if (passed.length) parts.push(el("h3", {}, t("passed", passed.length)), table(passed));
  els.tables.replaceChildren(...parts);
}

function table(rows) {
  const heads = [t("headStatus"), t("headReference"), t("headDoi"), t("headReason"), t("headEvidence")];
  const thead = el("thead", {}, el("tr", {}, ...heads.map((head) => el("th", { scope: "col" }, head))));
  const tbody = el("tbody");
  for (const row of rows) {
    const href = doiHref(row.doi);
    const doiCell = el("td", { "data-label": heads[2] });
    if (row.doi && href) doiCell.append(el("a", { href, rel: "noopener noreferrer", target: "_blank" }, row.doi));
    else doiCell.append(row.doi || "-");
    if (row.doi_note) doiCell.append(` (${row.doi_note === "resolved" ? t("resolved") : row.doi_note})`);
    tbody.append(
      el(
        "tr",
        { class: row.tone },
        el("td", { class: "verdict-cell" }, badge(row.label)),
        el(
          "td",
          { "data-label": heads[1] },
          el("div", { class: "ref-key" }, row.key),
          el("div", { class: "detail" }, row.detail),
        ),
        doiCell,
        el("td", { "data-label": heads[3] }, row.reason),
        row.evidence ? el("td", { class: "evidence", "data-label": heads[4] }, row.evidence) : el("td", { class: "evidence" }),
      ),
    );
  }
  return el("div", { class: "table-wrap" }, el("table", {}, thead, tbody));
}

function downloadReport() {
  if (!lastResult) return;
  const blob = new Blob([lastResult.report], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: "ref-verify-report.html" });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

for (const button of document.querySelectorAll(".lang button")) {
  button.addEventListener("click", () => {
    lang = button.dataset.lang;
    try {
      localStorage.setItem("ref-verify-lang", lang);
    } catch {
      // Not remembering the choice is fine.
    }
    applyLanguage();
  });
}
els.form.addEventListener("submit", onSubmit);
els.stop.addEventListener("click", onStop);
els.file.addEventListener("change", onFileChange);
els.fileClear.addEventListener("click", clearFile);
els.download.addEventListener("click", downloadReport);
// Start downloading the checker as soon as someone begins to use the form.
els.refs.addEventListener("focus", startWorker, { once: true });
applyLanguage();
