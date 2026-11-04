// Shared look for every report chart, so charts drawn on different days read as one set.
// Palette: the dataviz reference instance (validated categorical order, light surface). Slack shows the
// PNG on its own card, so charts are drawn on the light surface in both of Slack's themes.

export const theme = {
  width: 1200,
  height: 675,
  margin: { top: 88, right: 40, bottom: 56, left: 64 },
  surface: "#fcfcfb",
  text: { primary: "#0b0b0b", secondary: "#52514e", muted: "#7a7975" },
  grid: "#e6e5e1",
  axis: "#b9b8b2",
  // categorical slots in fixed order; never cycle past them (fold extras into "Other" or facet)
  series: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  // one-hue ramp for magnitude; ordinal marks start no lighter than step 250
  ramp: { 250: "#86b6ef", 400: "#3987e5", 450: "#2a78d6", 550: "#1c5cab", 650: "#104281" },
  band: "#cde2fb",                       // the "normal range" fill behind a series
  status: { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" },
  font: "Inter, 'DejaVu Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif",
  size: { title: 26, subtitle: 17, label: 14, small: 12 },
  line: 2,
  marker: 8,
};

// jsdom can't measure text; this is a deliberately generous estimate for layout and collision checks.
export function textWidth(str, size = theme.size.label) {
  return String(str).length * size * 0.56;
}

// Title (the finding, as a sentence) and subtitle (what is plotted, the window, the source).
// fixedSubtitle: the subtitle is fixed wording with no data in it (exempt from the number check).
export function header(svg, { title, subtitle, fixedSubtitle = false }) {
  const g = svg.append("g").attr("class", "header");
  g.append("text").attr("x", theme.margin.left).attr("y", 40)
    .attr("font-size", theme.size.title).attr("font-weight", 600).attr("fill", theme.text.primary).text(title);
  if (subtitle) {
    g.append("text").attr("x", theme.margin.left).attr("y", 66)
      .attr("font-size", theme.size.subtitle).attr("fill", theme.text.secondary).text(subtitle)
      .attr("data-number", fixedSubtitle ? "label" : null);
  }
  return g;
}

// Recessive axes: muted ink, no domain line on y, light grid. Tick text sits inside `.tick`, which the
// harness treats as scale output rather than a claimed number.
export function styleAxis(g, { grid = false, width = 0 } = {}) {
  g.selectAll("text").attr("fill", theme.text.secondary).attr("font-size", theme.size.small)
    .attr("font-family", theme.font);
  g.selectAll("line").attr("stroke", theme.axis);
  g.selectAll(".domain").attr("stroke", theme.axis);
  if (grid) {
    g.selectAll(".tick line").attr("x2", width).attr("stroke", theme.grid);
    g.select(".domain").remove();
  }
  return g;
}
