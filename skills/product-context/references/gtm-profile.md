# The GTM profile fields

The `profile` block in `<state>/gtm.json` is what `gtm.py` reads. product-context.md shows the same
values with their sources. Defaults come from `../../gtm/references/channel-fit.json` and
`../../gtm/references/funnel-templates.json`; read those files for the current numbers rather than
copying them here.

| field | allowed values | effect |
|---|---|---|
| `motion` | `self_serve`, `sales_assisted`, `enterprise`, `consumer_app`, `ecommerce`, `oss_devtool` | Picks the funnel template (stages, floors, which stage each conversion rung measures) and the column of the channel-fit matrix. The most consequential field. |
| `acv_usd` | number or `null` | Annual contract value (lifetime value for consumer and ecommerce). Feeds the economics factor: a channel whose typical cost per customer can't pay back at this deal size scores near 0 and drops out. `null` means "unknown" and economics is not applied, so set it as soon as you can. |
| `cycle_days` | number or `null` | Days from first touch to paid. Above the slow-cycle threshold, channels with fast feedback lose weight because results arrive too late to steer by. Also sets how far out a bet's check date should be. |
| `buying_committee` | `"1"`, `"2-4"`, `"5+"` | Not used in the fit maths yet. Skills read it: larger committees need proof, comparisons and sales material more than volume. |
| `attention` | `{channel: 0..1}` | Measured share of buyer attention per channel id (ids are the keys of `channels` in channel-fit.json). Missing means 1.0 (unmeasured). Set only from customer-research evidence. A low value rules a channel out with the reason "buyers aren't there". |
| `regulated` | `none`, `light`, `heavy` | Multiplies some channels down (see `compliance` in channel-fit.json) and tightens claims review in the writing skill. |
| `geo` | list of market codes | Not used in the fit maths yet. Outbound and lifecycle skills read it for consent and cold-email rules per country. |
| `confirmed` | `true` / `false` | Set with `gtm.py profile --confirm` only after the human approves the profile in a live conversation, never in a scheduled run. Any job that declares `requires: ["profile:confirmed"]` is skipped until then. Any change resets it to false. |

`stage` is not in the profile: it is the top-level `stage` in gtm.json (`prelaunch` or `launched`)
and decides which jobs run at all.

## Choosing the motion

| if the product… | motion |
|---|---|
| is bought by card on the website, no sales call needed | `self_serve` |
| offers a trial or demo, and a salesperson usually helps close | `sales_assisted` |
| sells to named large accounts with procurement, security review and a committee | `enterprise` |
| is a mobile or desktop app bought by individuals in a store | `consumer_app` |
| sells physical or digital goods through a cart | `ecommerce` |
| grows through installs of an open-source project, monetised by a paid tier or enterprise deals | `oss_devtool` |

When a product sits between two motions, pick the one that describes where most revenue comes
from today, and note the other in product-context.md. Revisit at `fit_review`.

## Checking the result

After editing the profile, run `python3 ../gtm/scripts/gtm.py fit`. For each channel it shows the
matrix value, attention, economics, cycle and compliance factors, the resulting fit, eligibility
and the reason. Show the human the ruled-out channels. If one is wrong, fix the field that caused
it; use `fit.overrides` in gtm.json only for a deliberate exception, and say why in the changelog.
