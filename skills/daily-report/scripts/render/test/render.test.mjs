import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { lint, shownNumbers, sourced, unsourced } from "../render.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const RENDER = join(HERE, "..", "render.mjs");
const DATA = join(HERE, "fixture-data.json");
const tmp = mkdtempSync(join(tmpdir(), "render-test-"));

function run(chart, extra = []) {
  const out = join(tmp, `${Math.random().toString(36).slice(2)}.png`);
  const r = spawnSync(process.execPath, [RENDER, "--chart", chart, "--data", DATA, "--out", out, ...extra],
    { encoding: "utf8" });
  return { status: r.status, out, json: r.stdout ? JSON.parse(r.stdout) : null, stderr: r.stderr };
}

function chart(body) {
  const p = join(tmp, `${Math.random().toString(36).slice(2)}.mjs`);
  writeFileSync(p, body);
  return p;
}

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47]);

test("starter charts render to PNG from the fixture", () => {
  for (const [c, opts] of [["weekly-band.mjs", '{"series":"daily:signup","label":"Signups"}'], ["funnel-floors.mjs", "{}"]]) {
    const r = run(join(HERE, "..", "charts", c), ["--opts", opts]);
    assert.equal(r.status, 0, JSON.stringify(r.json) + r.stderr);
    assert.deepEqual(readFileSync(r.out).subarray(0, 4), PNG);
    assert.deepEqual(r.json.unsourced, []);
  }
});

test("a number that isn't in the data fails the render", () => {
  const c = chart(`export default function draw({ svg }) { svg.append("text").text("42 new signups"); }`);
  const r = run(c);
  assert.equal(r.status, 2);
  assert.equal(r.json.unsourced[0].number, "42");
  assert.equal(existsSync(r.out), false);
  assert.equal(run(c, ["--allow-unsourced"]).status, 0);
});

test("numbers from the data pass, as written or as a percentage, and dates are ignored", () => {
  const c = chart(`export default function draw({ svg, data, d3 }) {
    const r = data.readings["daily:signup"];
    svg.append("text").text(\`\${r.this_week} this week, \${d3.format("+.0%")(r.change_pct)} since Oct 27, 2026\`);
  }`);
  assert.equal(run(c).status, 0);
});

test("lint rejects imports, fetch, process and d3 loaders", () => {
  assert.deepEqual(lint(`import fs from "fs"; export default function d() {}`), ["import"]);
  assert.ok(lint(`export default async function d() { await fetch("http://x"); }`).includes("fetch"));
  assert.ok(lint(`export default function d({d3}) { d3.json("http://x"); }`).includes("d3 network loaders"));
  assert.ok(lint(`export default function d() { ({}).constructor.constructor("return process")(); }`).includes("constructor"));
  assert.deepEqual(lint(`// fetch in a comment is fine\nexport default function d({ data }) { return data.window.start; }`), []);
  assert.deepEqual(lint(`function d() {}`), ["no `export default function`"]);
});

test("the sandbox blocks file reads outside the renderer even without the lint", () => {
  const c = chart(`export default function draw() { process.getBuiltinModule("fs").readFileSync("/etc/hosts"); }`);
  const r = run(c, ["--no-lint"]);
  assert.equal(r.status, 1);
  assert.match(r.json.message, /ERR_ACCESS_DENIED|permission/i);
});

test("the sandbox blocks the network where Node can (25+)", { skip: !process.allowedNodeEnvironmentFlags.has("--allow-net") }, () => {
  const c = chart(`export default async function draw() { await fetch("http://127.0.0.1:65530/"); }`);
  const r = run(c, ["--no-lint"]);
  assert.equal(r.status, 1);
  assert.match(r.json.message, /ERR_ACCESS_DENIED|permission/i);
});

test("the sandbox blocks child processes", () => {
  const c = chart(`export default function draw() { process.getBuiltinModule("child_process").execSync("true"); }`);
  const r = run(c, ["--no-lint"]);
  assert.equal(r.status, 1);
  assert.match(r.json.message, /ERR_ACCESS_DENIED|permission/i);
});

test("number parsing", () => {
  assert.deepEqual(shownNumbers("Nov 2, 2026: 1,204 visits, 7.0% convert, 2026-11-02").map((n) => n.shown), ["1,204", "7.0%"]);
  assert.ok(sourced({ value: 7.0, decimals: 1, suffix: "%" }, [0.0701]));
  assert.ok(!sourced({ value: 7.2, decimals: 1, suffix: "%" }, [0.0701]));
  assert.ok(sourced({ value: 1.2, decimals: 1, suffix: "k" }, [1204]));
  assert.deepEqual(unsourced([{ text: "100", tick: true }, { text: "95% interval", exempt: true }], {}), []);
});
