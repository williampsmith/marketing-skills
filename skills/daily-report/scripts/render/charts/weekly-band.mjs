// Starting point: one daily series as whole weeks against its normal range, with the operator's own
// actions marked under the weeks they happened in. Copy and adapt; don't feel bound to it.
//
// opts: { series: "daily:signup", label: "Signups", title?: "…" }
// data: readings[series] from report_data.py (weeks, median_before, band, verdict, change_pct), actions.
export default function draw({ d3, svg, data, opts, theme, width, height, helpers }) {
  const r = data.readings[opts.series];
  if (!r || !r.weeks || !r.weeks.length) throw new Error(`no reading for ${opts.series}`);
  const label = opts.label || opts.series;
  const weeks = r.weeks;
  const m = theme.margin;
  const fmtPct = d3.format("+.0%");
  const title = opts.title || ({
    unusually_high: `${label} are up: ${r.this_week} this week against a usual ${r.median_before}`,
    unusually_low: `${label} are down: ${r.this_week} this week against a usual ${r.median_before}`,
    normal: `${label} are within their normal range this week`,
    too_little_data: `${label}: too little data yet to call a change`,
  }[r.verdict] || label);
  const sub = `Weekly totals, ${data.window.start} to ${data.window.end}` +
    (r.change_pct != null ? ` · ${fmtPct(r.change_pct)} against the median of earlier weeks` : "") +
    (r.band ? " · shaded: normal range" : "");
  helpers.header(svg, { title, subtitle: sub });

  const innerW = width - m.left - m.right;
  const innerH = height - m.top - m.bottom - 36; // room for the action strip
  const g = svg.append("g").attr("transform", `translate(${m.left},${m.top})`);
  const x = d3.scaleBand().domain(weeks.map((w) => w.end)).range([0, innerW]).padding(0.25);
  const top = d3.max([...weeks.map((w) => w.value), ...(r.band ? [r.band[1]] : [])]) || 1;
  const y = d3.scaleLinear().domain([0, top]).nice().range([innerH, 0]);

  g.append("g").call(d3.axisLeft(y).ticks(5).tickSize(-innerW).tickPadding(8))
    .call((a) => helpers.styleAxis(a, { grid: true, width: innerW }));
  g.append("g").attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).tickFormat((d) => d3.utcFormat("%b %-d")(new Date(d + "T00:00:00Z"))).tickSizeOuter(0))
    .call((a) => helpers.styleAxis(a));

  if (r.band) {
    g.append("rect").attr("x", 0).attr("width", innerW)
      .attr("y", y(Math.min(r.band[1], y.domain()[1]))).attr("height", y(Math.max(r.band[0], 0)) - y(Math.min(r.band[1], y.domain()[1])))
      .attr("fill", theme.band).attr("opacity", 0.6);
    g.append("line").attr("x1", 0).attr("x2", innerW).attr("y1", y(r.median_before)).attr("y2", y(r.median_before))
      .attr("stroke", theme.ramp[550]).attr("stroke-dasharray", "4 4").attr("stroke-width", 1.5);
  }
  const last = weeks[weeks.length - 1].end;
  g.selectAll("rect.bar").data(weeks).join("rect").attr("class", "bar")
    .attr("x", (w) => x(w.end)).attr("width", x.bandwidth())
    .attr("y", (w) => y(w.value)).attr("height", (w) => innerH - y(w.value)).attr("rx", 4)
    .attr("fill", (w) => (w.end === last ? theme.series[0] : theme.ramp[250]));
  const lw = weeks[weeks.length - 1];
  g.append("text").attr("x", x(lw.end) + x.bandwidth() / 2).attr("y", y(lw.value) - 8).attr("text-anchor", "middle")
    .attr("font-size", theme.size.label).attr("font-weight", 600).attr("fill", theme.text.primary).text(lw.value);

  // what the operator did, under the week it happened in
  const acts = (data.actions || []).filter((a) => a.kind !== "send");
  const weekOf = (d) => weeks.find((w) => d >= w.start && d <= w.end);
  const strip = g.append("g").attr("transform", `translate(0,${innerH + 40})`);
  const byWeek = d3.group(acts.filter((a) => weekOf(a.date)), (a) => weekOf(a.date).end);
  for (const [end, list] of byWeek) {
    const cx = x(end) + x.bandwidth() / 2;
    strip.append("circle").attr("cx", cx).attr("cy", 0).attr("r", theme.marker / 2).attr("fill", theme.series[1]);
    if (list.length > 1) {
      strip.append("text").attr("x", cx + 8).attr("y", 4).attr("font-size", theme.size.small)
        .attr("fill", theme.text.secondary).text(`×${list.length}`).attr("data-number", "label");
    }
  }
  if (byWeek.size) {
    strip.append("text").attr("x", -8).attr("y", 4).attr("text-anchor", "end").attr("font-size", theme.size.small)
      .attr("fill", theme.text.secondary).text("shipped");
  }
}
