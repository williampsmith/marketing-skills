// The sandboxed half of the renderer. render.mjs starts this file in a Node process with the permission
// model on: it may read only the renderer's own folder, the chart and the data, write nothing, open no
// network connection (Node 25+), start no process or worker, and load no native addon. It runs the chart module
// against a jsdom SVG and prints {svg, texts} as JSON on stdout.
import { readFileSync, writeSync } from "node:fs";
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
// The chart can reach the jsdom window (svg.node().ownerDocument.defaultView). Take away everything
// on it that talks to the network, as a second fence for Node versions whose sandbox can't block it.
for (const k of ["XMLHttpRequest", "WebSocket", "EventSource", "fetch", "Request", "Response", "Headers",
                 "Worker", "SharedWorker", "Image", "Audio", "open"]) {
  try { delete dom.window[k]; } catch { /* non-configurable: leave it */ }
  try { Object.defineProperty(dom.window, k, { value: undefined, configurable: false }); } catch { /* ignore */ }
}
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

// Serialize as XML (resvg rejects HTML entities such as &nbsp;) and hand it back on fd 3, so a chart's
// console.log can't corrupt the result. The parent re-reads everything it checks from this SVG.
const out = new dom.window.XMLSerializer().serializeToString(svg.node());
writeSync(3, out);
