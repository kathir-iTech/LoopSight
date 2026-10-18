const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const ts = require("typescript");

// Exercise the real route handlers and NextResponse without a second web server.
const source = path.resolve(__dirname, "../src");
const modules = new Map();
function loadTs(file) {
  if (modules.has(file)) return modules.get(file).exports;
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  modules.set(file, module);
  const nativeRequire = createRequire(file);
  function resolve(name) {
    if (name.startsWith("@/")) return loadTs(path.join(source, name.slice(2) + ".ts"));
    return nativeRequire(name);
  }
  new Function("require", "module", "exports", compiled)(resolve, module, module.exports);
  return module.exports;
}
const { POST } = loadTs(path.join(source, "app/api/inspect/route.ts"));
const { GET } = loadTs(path.join(source, "app/api/jobs/[id]/route.ts"));
const savedFetch = global.fetch;
const variables = ["VERCEL", "INFERENCE_API_URL", "DEMO_MODE", "DEMO_CASE", "FAIL_CLOSED_PROD"];
let savedEnv;
test.beforeEach(() => {
  savedEnv = Object.fromEntries(variables.map((key) => [key, process.env[key]]));
  for (const key of variables) delete process.env[key];
  process.env.VERCEL = "1";
});
test.afterEach(() => {
  global.fetch = savedFetch;
  for (const [key, value] of Object.entries(savedEnv)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});
function inspection(fields = {}) {
  const form = new FormData();
  form.set("image", new File(["not-an-image"], "upload.png"));
  for (const [key, value] of Object.entries(fields)) form.set(key, value);
  return POST(new Request("http://example.test/api/inspect", { method: "POST", body: form }));
}
function job(id) {
  return GET(new Request("http://example.test/api/jobs/" + id), { params: Promise.resolve({ id }) });
}

test("missing Vercel backend never produces a fixture verdict", async () => {
  const response = await inspection();
  assert.equal(response.status, 503);
  assert.equal((await response.json()).job_id, undefined);
});
test("an unreachable configured backend never produces a fixture verdict", async () => {
  process.env.INFERENCE_API_URL = "http://backend.test";
  global.fetch = async () => { throw new Error("offline"); };
  assert.equal((await inspection()).status, 503);
  assert.equal((await job("anything" )).status, 503);
});
test("backend validation errors retain their status and details", async () => {
  process.env.INFERENCE_API_URL = "http://backend.test";
  global.fetch = async () => Response.json({ detail: "could not decode image" }, { status: 400 });
  const response = await inspection();
  assert.equal(response.status, 400);
  assert.match((await response.json()).detail, /decode/);
});
test("unknown backend jobs remain 404 rather than a successful mock", async () => {
  process.env.INFERENCE_API_URL = "http://backend.test";
  global.fetch = async () => Response.json({ detail: "Job not found" }, { status: 404 });
  assert.equal((await job("missing")).status, 404);
});
test("a caller cannot enable demo mode through form fields", async () => {
  process.env.INFERENCE_API_URL = "http://backend.test/";
  global.fetch = async (url, options) => {
    assert.equal(url, "http://backend.test/inspect");
    assert.equal(options.body.get("demo_case"), null);
    return Response.json({ job_id: "real-id" });
  };
  const response = await inspection({ demo_case: "confident_pass" });
  assert.deepEqual(await response.json(), { job_id: "real-id" });
});
test("synthetic benchmarks are forwarded for actual OpenCV execution", async () => {
  process.env.INFERENCE_API_URL = "http://backend.test";
  global.fetch = async (url, options) => {
    assert.equal(url, "http://backend.test/inspect/sample/water_turbid_fail");
    assert.equal(options.body, undefined);
    return Response.json({ job_id: "benchmark-id" });
  };
  assert.equal((await inspection({ sample_id: "water_turbid_fail" })).status, 200);
});
test("explicit fixtures carry provenance through creation and retrieval", async () => {
  process.env.DEMO_MODE = "golden";
  global.fetch = async () => { throw new Error("demo must not contact a backend"); };
  const response = await inspection({ sample_id: "water_turbid_fail" });
  assert.equal(response.status, 200);
  const data = await response.json();
  assert.equal(data.result.provenance.execution_mode, "demo_fixture");
  assert.equal((await (await job(data.job_id)).json()).provenance.execution_mode, "demo_fixture");
  assert.equal((await job("this-job-never-existed")).status, 404);
  assert.equal((await job("missing-crack-job")).status, 404);
  assert.equal((await job("__proto__")).status, 404);
  assert.equal((await job("constructor")).status, 404);
});
test("timeouts return a gateway error without a verdict", async () => {
  process.env.INFERENCE_API_URL = "http://backend.test";
  global.fetch = async () => { throw new DOMException("timed out", "AbortError"); };
  const response = await inspection();
  assert.equal(response.status, 504);
  assert.equal((await response.json()).job_id, undefined);
});
test("malformed forms return 400", async () => {
  const response = await POST(new Request("http://example.test/api/inspect", { method: "POST", body: "oops" }));
  assert.equal(response.status, 400);
});
