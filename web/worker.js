// Runs the ref-verify engine in Pyodide off the main thread. Synchronous XHR is allowed
// here, which lets the Python engine keep its blocking HTTP calls and pacing.
// Pyodide 314 only loads in a module worker: new Worker("worker.js", { type: "module" }).
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

const ready = (async () => {
  const started = performance.now();
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  const [archive, glue] = await Promise.all([
    fetch("ref_verify.zip").then((r) => {
      if (!r.ok) throw new Error("ref_verify.zip: HTTP " + r.status);
      return r.arrayBuffer();
    }),
    fetch("engine.py").then((r) => {
      if (!r.ok) throw new Error("engine.py: HTTP " + r.status);
      return r.text();
    }),
  ]);
  const lib = "/home/pyodide/lib";
  pyodide.FS.mkdirTree(lib);
  pyodide.unpackArchive(archive, "zip", { extractDir: lib });
  pyodide.FS.writeFile(lib + "/ref_verify_web.py", glue);
  pyodide.runPython(`import sys; sys.path.insert(0, "${lib}")`);
  const engine = pyodide.pyimport("ref_verify_web");
  const version = pyodide.pyimport("ref_verify").__version__;
  postMessage({ type: "ready", ms: Math.round(performance.now() - started), version });
  return engine;
})();

ready.catch((error) => postMessage({ type: "load-error", message: String(error) }));

onmessage = async (event) => {
  const { name, bytes } = event.data;
  let engine;
  try {
    engine = await ready;
  } catch {
    return;
  }
  const started = performance.now();
  try {
    const out = engine.check(name, bytes, (done, total) => {
      postMessage({ type: "progress", done, total, ms: Math.round(performance.now() - started) });
    });
    postMessage({ type: "done", result: JSON.parse(out), ms: Math.round(performance.now() - started) });
  } catch (error) {
    postMessage({ type: "run-error", message: String(error) });
  }
};
