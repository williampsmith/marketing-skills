// Starting point: each funnel step's conversion with its 95% interval against the floor it should
// clear. A dot whose whole interval sits left of the floor is a real shortfall; one straddling the
// floor is not yet a finding. Copy and adapt.
//
// opts: { title?: "…" }
// data: funnel.steps from report_data.py (rate, interval, floor, vs_floor, label).
export default function draw({ d3, svg, data, opts, theme, width, height, helpers }) {
  const steps = data.funnel.steps.filter((s) => s.rate != null && s.interval);
  const m = theme.margin;
  const below = steps.filter((s) => s.vs_floor === "below");
  const title = opts.title || (steps.length === 0
    ? "Not enough funnel data yet to compare against floors"
    : below.length
      ? `${below[0].label} converts below its floor, and the gap is larger than the noise`
      : "No funnel step is clearly below its floor");
  helpers.header(svg, { title, subtitle: "Conversion from the previous step, last 28 days · bar: 95% interval · tick: floor",
    fixedSubtitle: true });
  if (!steps.length) return;

  const labelW = d3.max(steps, (s) => helpers.textWidth(s.label, theme.size.label)) + 16;
  const innerW = width - m.left - m.right - labelW;
  const innerH = height - m.top - m.bottom;
  const g = svg.append("g").attr("transform", `translate(${m.left + labelW},${m.top})`);
  const hi = d3.max(steps, (s) => Math.max(s.interval[1], s.floor || 0));
  const x = d3.scaleLinear().domain([0, Math.min(1, hi * 1.15)]).nice().range([0, innerW]);
  const y = d3.scaleBand().domain(steps.map((s) => s.id)).range([0, innerH]).padding(0.45);

  g.append("g").attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(6).tickFormat(d3.format(".0%")).tickSize(-innerH).tickPadding(8))
    .call((a) => helpers.styleAxis(a)).call((a) => a.selectAll(".tick line").attr("stroke", theme.grid))
    .call((a) => a.select(".domain").remove());

  for (const s of steps) {
    const cy = y(s.id) + y.bandwidth() / 2;
    const color = s.vs_floor === "below" ? theme.status.critical : theme.series[0];
    g.append("text").attr("x", -16).attr("y", cy + 5).attr("text-anchor", "end")
      .attr("font-size", theme.size.label).attr("fill", theme.text.primary).text(s.label);
    g.append("line").attr("x1", x(s.interval[0])).attr("x2", x(s.interval[1])).attr("y1", cy).attr("y2", cy)
      .attr("stroke", color).attr("stroke-width", 6).attr("stroke-linecap", "round").attr("opacity", 0.35);
    if (s.floor != null) {
      g.append("line").attr("x1", x(s.floor)).attr("x2", x(s.floor)).attr("y1", cy - 14).attr("y2", cy + 14)
        .attr("stroke", theme.text.primary).attr("stroke-width", 2);
    }
    g.append("circle").attr("cx", x(s.rate)).attr("cy", cy).attr("r", theme.marker / 2 + 1).attr("fill", color)
      .attr("stroke", theme.surface).attr("stroke-width", 2);
    g.append("text").attr("x", x(Math.max(s.interval[1], s.floor || 0)) + 12).attr("y", cy + 5)
      .attr("font-size", theme.size.small).attr("fill", theme.text.secondary)
      .text(`${d3.format(".1%")(s.rate)} (floor ${d3.format(".1%")(s.floor)})`);
  }
}
