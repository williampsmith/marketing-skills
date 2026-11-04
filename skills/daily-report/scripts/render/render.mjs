#!/usr/bin/env node
// Render an agent-written D3 chart to PNG.
//
//   node render.mjs --chart <chart.mjs> --data <data.json> --out <chart.png>
//                   [--opts '{"series":"daily:signup"}'] [--width 1200] [--height 675] [--scale 2]
//                   [--allow-unsourced]
//
// 1. Lint: the chart is a plain ES module with one default export. It may not import, require, reach
//    for process, fetch, sockets, eval or Function. A guard against mistakes only: it is easy to get
//    round on purpose (string-built names), so the sandbox and the parent's checks are the fence.
// 2. Draw in a sandbox (draw.mjs): Node's permission model, reads limited to this folder + the chart +
//    the data, no writes, no network (Node 25+; on older Node the render is refused unless
//    --allow-open-network), no child processes, workers or addons. (Code generation stays on: jsdom's
//    selector engine compiles selectors with Function; the lint keeps it out of chart code.)
// 3. Check the SVG in this (trusted) process, never trusting the sandbox's report: the root keeps the
//    requested size; no href, url() or @import points outside the document (resvg would read local
//    files outside the sandbox); and every number in a visible text (outside axis ticks) must be a value in the data,
//    as written or as a percentage, at the precision shown. Dates are ignored. Text inside an element
//    with data-number="label" is exempt (e.g. "95% interval"). Unsourced numbers fail the render
//    unless --allow-unsourced, and are listed either way.
// 4. Rasterize the SVG with resvg (trusted code, outside the sandbox). Fonts: system fonts, ./fonts and
//    $RENDER_FONT_DIR.
//
// Prints a JSON result. Exit 0 rendered, 1 usage or draw error, 2 lint or unsourced-number failure.
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync, realpathSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";
import { theme } from "./theme.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));

export const FORBIDDEN = [
  [/\bimport\b/, "import"], [/\brequire\s*\(/, "require()"], [/\bprocess\b/, "process"],
  [/\bglobalThis\b/, "globalThis"], [/\bfetch\b/, "fetch"], [/\bXMLHttpRequest\b/, "XMLHttpRequest"],
  [/\bWebSocket\b/, "WebSocket"], [/\beval\b/, "eval"], [/\bFunction\b/, "Function"],
  [/\bconstructor\b/, "constructor"], [/\bchild_process\b/, "child_process"],
  [/(?<![.\w$])window\b/, "window"], [/(?<![.\w$])document\b/, "document"],
  [/\bd3\s*\.\s*(json|csv|tsv|dsv|text|xml|html|svg|image|blob|buffer)\s*\(/, "d3 network loaders"],
];

export function lint(src) {
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  const bad = FORBIDDEN.filter(([re]) => re.test(code)).map(([, name]) => name);
  if (!/export\s+default\s+(async\s+)?function/.test(code)) bad.push("no `export default function`");
  return bad;
}

// Real month words only (capitalised, whole word), so "Marketing 37%" or "Declined 61" stay checked.
const MONTHS = "(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
  + "Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\\b\\.?";
const DATE_PATTERNS = [
  /\b\d{4}-\d{2}-\d{2}\b/g,
  new RegExp(`\\b${MONTHS}\\s+\\d{1,2}(?:,?\\s+\\d{4})?\\b`, "g"),
  new RegExp(`\\b\\d{1,2}\\s+${MONTHS}(?:\\s+\\d{4})?`, "g"),
  new RegExp(`\\b${MONTHS}\\s+\\d{4}\\b`, "g"),
];
// Raw daily series are left out of the pool: with 84 values per stage, almost any small integer would
// match by coincidence. Label a value from readings, funnel, bets or spend instead.
const EXCLUDED_KEYS = new Set(["series"]);

export function dataNumbers(data) {
  const out = [];
  const walk = (v) => {
    if (typeof v === "number" && Number.isFinite(v)) out.push(v);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === "object") {
      for (const [k, x] of Object.entries(v)) if (!EXCLUDED_KEYS.has(k)) walk(x);
    }
  };
  walk(data);
  return out;
}

// Numbers shown in a text, with the precision each was written at. Dates are removed first.
export function shownNumbers(text) {
  let t = String(text);
  for (const re of DATE_PATTERNS) t = t.replace(re, " ");
  const out = [];
  for (const m of t.matchAll(/([-−+]?)(\d[\d,]*(?:\.\d+)?)\s*(%|k\b|K\b|M\b)?/g)) {
    const raw = m[2].replace(/,/g, "");
    const decimals = raw.includes(".") ? raw.split(".")[1].length : 0;
    const sign = m[1] === "+" ? 1 : m[1] ? -1 : 0; // 0: no sign shown
    out.push({ shown: m[0].trim(), value: Number(raw), decimals, suffix: m[3] || "", sign });
  }
  return out;
}

// A shown sign must match the data's sign ("-51" is not +51); an unsigned number matches either
// ("down 12%" from -0.12). Only a % number is compared against fractions ×100.
export function sourced(n, values) {
  const tol = 0.5 * 10 ** -n.decimals + 1e-9;
  const scale = n.suffix === "k" || n.suffix === "K" ? 1e3 : n.suffix === "M" ? 1e6 : 1;
  return values.some((v) => {
    if (n.sign > 0 && v < 0) return false;
    if (n.sign < 0 && v > 0) return false;
    const a = Math.abs(v);
    const cands = n.suffix === "%" ? [a * 100, a] : [a / scale];
    return cands.some((c) => Math.abs(c - n.value) <= tol);
  });
}

export function unsourced(texts, data, opts = {}) {
  const values = dataNumbers(data).concat(dataNumbers(opts.allowed || []));
  const bad = [];
  for (const t of texts) {
    if (t.tick || t.exempt) continue;
    for (const n of shownNumbers(t.text)) if (!sourced(n, values)) bad.push({ text: t.text, number: n.shown });
  }
  return bad;
}

function args(argv) {
  const a = { width: theme.width, height: theme.height, scale: 2, opts: "{}", allowUnsourced: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    const v = () => argv[++i];
    if (k === "--chart") a.chart = v();
    else if (k === "--data") a.data = v();
    else if (k === "--out") a.out = v();
    else if (k === "--opts") a.opts = v();
    else if (k === "--width") a.width = Number(v());
    else if (k === "--height") a.height = Number(v());
    else if (k === "--scale") a.scale = Number(v());
    else if (k === "--allow-unsourced") a.allowUnsourced = true;
    else if (k === "--allow-open-network") a.allowOpenNetwork = true;
    else if (k === "--no-lint") a.noLint = true; // tests only: proves the sandbox holds without the lint
    else throw new Error(`unknown argument ${k}`);
  }
  if (!a.chart || !a.data || !a.out) throw new Error("--chart, --data and --out are required");
  return a;
}

export function sandboxFlags() {
  const flags = process.allowedNodeEnvironmentFlags;
  if (!flags.has("--permission")) {
    throw new Error(`Node ${process.version} has no permission model; use Node 26 (LTS) or 25+`);
  }
  return { network: flags.has("--allow-net") };
}

// What the parent checks in the SVG the sandbox returned. Everything here is read from the SVG itself,
// never from anything the chart reported.
export function inspect(svgText, { width, height }) {
  const dom = new JSDOM(svgText, { contentType: "image/svg+xml" });
  const doc = dom.window.document;
  const root = doc.documentElement;
  const problems = [];
  if (!root || root.nodeName.toLowerCase() !== "svg") problems.push("the result isn't an <svg>");
  else {
    if (Number(root.getAttribute("width")) !== width || Number(root.getAttribute("height")) !== height) {
      problems.push(`the root <svg> must stay ${width}×${height}`);
    }
    if ((root.getAttribute("viewBox") || "") !== `0 0 ${width} ${height}`) {
      problems.push(`the root viewBox must stay "0 0 ${width} ${height}"`);
    }
  }
  // No external references of any kind: resvg would read local files outside the sandbox.
  for (const el of doc.querySelectorAll("*")) {
    for (const at of Array.from(el.attributes)) {
      const v = at.value.trim();
      if (/(^|:)href$/i.test(at.name) && !(v.startsWith("#") || /^data:image\/(png|jpeg|gif|webp);base64,/i.test(v))) {
        problems.push(`external reference not allowed: <${el.nodeName} ${at.name}="${v.slice(0, 80)}">`);
      }
      for (const m of v.matchAll(/url\(\s*['"]?([^'")\s]*)/gi)) {
        if (!m[1].startsWith("#")) problems.push(`external url() not allowed in ${at.name}: ${m[1].slice(0, 80)}`);
      }
    }
    if (el.nodeName.toLowerCase() === "style" && /@import|url\(\s*['"]?(?!#)/i.test(el.textContent)) {
      problems.push("external references not allowed in <style>");
    }
  }
  const texts = [];
  for (const el of doc.querySelectorAll("text")) {
    texts.push({
      text: el.textContent,
      tick: Boolean(el.closest(".tick")),
      exempt: Boolean(el.closest('[data-number="label"]')),
    });
  }
  return { problems, texts };
}

export function draw({ chart, data, opts = "{}", width = theme.width, height = theme.height, allowOpenNetwork = false }) {
  const { network } = sandboxFlags();
  if (!network && !allowOpenNetwork) {
    throw new Error(`Node ${process.version} can't block the chart from the network; use Node 26 (LTS) or 25+, `
      + "or pass --allow-open-network to accept that the chart code could send data out");
  }
  const reads = [HERE, chart, data].map((p) => `--allow-fs-read=${realpathSync(p)}`);
  const res = spawnSync(process.execPath, [
    "--permission", ...reads,
    join(HERE, "draw.mjs"), realpathSync(chart), realpathSync(data), opts, String(width), String(height),
  ], { encoding: "utf8", timeout: 30_000, maxBuffer: 32 * 1024 * 1024, env: { NODE_OPTIONS: "" },
    stdio: ["ignore", "pipe", "pipe", "pipe"] });
  if (res.error) throw res.error;
  if (res.status !== 0) {
    const lines = (res.stderr || "").split("\n").filter((l) => l.trim() && !/^\s+at /.test(l) && !/^node:internal|^\s*\^|triggerUncaught/.test(l));
    const err = new Error(`chart failed: ${lines.slice(0, 8).join("\n")}`);
    err.stderr = res.stderr;
    throw err;
  }
  const svg = res.output[3] || "";
  if (!svg) throw new Error("the chart produced no SVG");
  return { svg, networkBlocked: network };
}

export async function rasterize(svg, { scale = 2, width = theme.width, background = theme.surface } = {}) {
  const { Resvg } = await import("@resvg/resvg-js");
  const fontDirs = [join(HERE, "fonts"), process.env.RENDER_FONT_DIR].filter((d) => d && existsSync(d));
  const r = new Resvg(svg, {
    fitTo: { mode: "width", value: Math.round(width * scale) },
    background,
    font: { loadSystemFonts: true, fontDirs, defaultFontFamily: "DejaVu Sans" },
  });
  if (r.imagesToResolve().length) throw new Error("the SVG references images resvg would load from outside");
  return r.render().asPng();
}

async function main() {
  let a;
  try {
    a = args(process.argv.slice(2));
  } catch (e) {
    console.error(e.message);
    return 1;
  }
  const result = { chart: a.chart, out: a.out };
  if (!a.noLint) {
    const bad = lint(readFileSync(a.chart, "utf8"));
    if (bad.length) {
      console.log(JSON.stringify({ ...result, error: "lint", forbidden: bad }, null, 2));
      return 2;
    }
  }
  let drawn;
  try {
    JSON.parse(a.opts);
    drawn = draw({ chart: a.chart, data: a.data, opts: a.opts, width: a.width, height: a.height,
      allowOpenNetwork: a.allowOpenNetwork });
  } catch (e) {
    console.log(JSON.stringify({ ...result, error: "draw", message: e.message }, null, 2));
    return 1;
  }
  const data = JSON.parse(readFileSync(a.data, "utf8"));
  let seen;
  try {
    seen = inspect(drawn.svg, { width: a.width, height: a.height });
  } catch (e) {
    console.log(JSON.stringify({ ...result, error: "svg", message: e.message }, null, 2));
    return 2;
  }
  if (seen.problems.length) {
    console.log(JSON.stringify({ ...result, error: "svg", problems: seen.problems }, null, 2));
    return 2;
  }
  const bad = unsourced(seen.texts, data, JSON.parse(a.opts));
  result.network_blocked = drawn.networkBlocked;
  result.unsourced = bad;
  if (bad.length && !a.allowUnsourced) {
    console.log(JSON.stringify({ ...result, error: "unsourced numbers: compute them in the data layer, "
      + "or mark a fixed label with data-number=\"label\"" }, null, 2));
    return 2;
  }
  let png;
  try {
    png = await rasterize(drawn.svg, { scale: a.scale, width: a.width });
  } catch (e) {
    console.log(JSON.stringify({ ...result, error: "rasterize", message: e.message }, null, 2));
    return 1;
  }
  mkdirSync(dirname(resolve(a.out)), { recursive: true });
  writeFileSync(a.out, png);
  writeFileSync(a.out.replace(/\.png$/i, "") + ".svg", drawn.svg);
  console.log(JSON.stringify({ ...result, png: a.out, bytes: png.length, width: a.width * a.scale,
    height: a.height * a.scale }, null, 2));
  return 0;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main();
}
