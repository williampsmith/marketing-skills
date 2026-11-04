# Writing a chart

A chart is an ES module with one default export. The renderer calls it with a jsdom SVG already
sized and filled with the surface colour:

```js
export default function draw({ d3, svg, data, opts, theme, width, height, helpers }) {
  // d3: all of D3 except its loaders (json, csv, text, …): draw the data you're given
  // svg: a d3 selection of the <svg>; append to it
  // data: data.json from report_data.py, frozen
  // opts: whatever you pass with --opts '{…}' (series name, label, title)
  // theme: colours, fonts, sizes, margin (scripts/render/theme.mjs)
  // helpers.header(svg, {title, subtitle, fixedSubtitle}), helpers.styleAxis(g, {grid, width}),
  // helpers.textWidth(str, size): an estimate, since jsdom can't measure text
}
```

Don't `import`, `require`, or use `process`, `fetch`, `window`, `document`, `eval`, `Function` or
`constructor`; a lint flags those, as a guard against mistakes. The fence is elsewhere: the chart runs
in a Node process that can read only the renderer, the chart and the data, and can't write, start
processes or use the network (Node 25+), with the network objects removed from its window. The
parent then checks the SVG it gets back: the root keeps its size, nothing references a file or URL
outside the document (no `<image href>` to a path; embed a `data:image/png;base64,…` if you must),
and the numbers come from the data.

## What makes a good report chart

- **The title is the finding**, as a sentence with its numbers ("Signups are up: 51 this week
  against a usual 26"). The subtitle says what is plotted, the window and the source.
- **Pick the form for the job** (the dataviz method): change over time → weekly bars or a line with
  the normal band; conversion against a target → dots with interval whiskers and the floor as a tick;
  composition → a stacked bar with at most four segments; one number → a big number with its context
  line, not a chart. Never two y-axes; index to a common base or draw two charts.
- **Show the noise.** Draw the normal band (`readings[…].band`) or the interval (`funnel.steps[…].interval`)
  whenever the data has one. A chart that hides uncertainty overstates the finding.
- **Mark what the operator did** (`data.actions`) on time charts, small and below the plot, so the
  reader can see what happened the week a number moved.
- **Colours** from `theme`: `theme.series` in order for identities (never cycle past eight; fold to
  "Other"), `theme.ramp` for magnitude, `theme.status` only for good/bad states and never alone
  (pair with a label). Text is in `theme.text` inks, never series colours.
- **Labels**: label the point that matters, not every point. One series needs no legend; two to four
  get direct labels. Leave room: Slack shows the image about 600px wide on a laptop, so keep text at
  `theme.size.small` or larger at the default 1200×675 drawn at 2×.
- The PNG is static: no hover, so anything a reader needs must be on the image.

## The number check

After drawing, the renderer reads every visible text outside axis ticks and checks each number in it
against the numbers in data.json, as written or (for a `%`) as a percentage, at the precision shown
(`7.0%` matches 0.0701; `1.2k` matches 1204). A sign you show must match the data's sign (`-51` is
not 51); an unsigned number may stand for either ("down 12%"). Dates written with month names or as
YYYY-MM-DD are ignored. The raw daily `series` don't count as a source (with 84 values per stage,
almost any small number would match): label values from `readings`, `funnel`, `bets` or `spend`. A fixed label with a number in it
("95% interval") goes in an element with `data-number="label"`, or pass `fixedSubtitle: true` to
`helpers.header`. `--allow-unsourced` renders anyway and lists what didn't match; use it only for a
number you computed in the chart from shown values (a sum of two bars), and say so in the message.
