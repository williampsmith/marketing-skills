// The sandboxed half of the renderer. render.mjs starts this file in a Node process with the permission
// model on: it may read only the renderer's own folder, the chart and the data, write nothing, open no
// network connection (Node 25+), start no process or worker, and load no native addon. It runs the chart module
// against a jsdom SVG and prints {svg, texts} as JSON on stdout.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { JSDOM } from "jsdom";
import * as d3all from "d3";
import { theme, textWidth, header, styleAxis } from "./theme.mjs";

// d3 without its loaders: a chart draws the data it is given and fetches nothing
const LOADERS = ["json", "csv", "tsv", "dsv", "text", "xml", "html", "svg", "image", "blob", "buffer"];
const d3 = Object.freeze(Object.fromEntries(Object.entries(d3all).filter(([k]) => !LOADERS.includes(k))));

const [chartPath, dataPath, optsJson, w, h] = process.argv.slice(2);
const width = Number(w) || theme.width;
const height = Number(h) || theme.height;

function deepFreeze(o) {
  if (o && typeof o === "object" && !Object.isFrozen(o)) {
    Object.freeze(o);
    for (const v of Object.values(o)) deepFreeze(v);
  }
  return o;
}

const data = deepFreeze(JSON.parse(readFileSync(dataPath, "utf8")));
const opts = deepFreeze(JSON.parse(optsJson || "{}"));

const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.document = dom.window.document; // d3.create and friends look for a global document

const svg = d3.select(dom.window.document.body).append("svg")
  .attr("xmlns", "http://www.w3.org/2000/svg")
  .attr("width", width).attr("height", height).attr("viewBox", `0 0 ${width} ${height}`)
  .attr("font-family", theme.font);
svg.append("rect").attr("width", width).attr("height", height).attr("fill", theme.surface);

const mod = await import(pathToFileURL(chartPath).href);
if (typeof mod.default !== "function") {
  throw new Error("the chart module must `export default function draw({ d3, svg, data, opts, theme, width, height, helpers })`");
}
await mod.default({ d3, svg, data, opts, theme, width, height, helpers: { textWidth, header, styleAxis } });

// Every visible text with whether it is scale output (axis ticks) or explicitly exempted, for the
// harness's "numbers come from the data" check.
const texts = [];
for (const el of dom.window.document.querySelectorAll("svg text")) {
  if (el.parentNode && el.parentNode.closest && el.parentNode.closest("text")) continue; // tspans: counted once
  texts.push({
    text: el.textContent,
    tick: Boolean(el.closest(".tick")),
    exempt: el.closest("[data-number=label]") ? true : false,
  });
}
process.stdout.write(JSON.stringify({ svg: svg.node().outerHTML, texts }));
