# Revenue sources

Revenue is pluggable: `gtm.py connect revenue <source>`. Every source ends in PostHog, and the agent
reads it there with the same query-only key. **The plugin's scripts never hold a billing key.** A
human connects billing systems to PostHog once.

Checked 2026-11-01. HogQL table and column names below are illustrative: PostHog names warehouse
tables per connection (often with a prefix you choose), so **verify against your project's
schema** before saving any query. Look first, e.g.
`python3 scripts/posthog.py query "SELECT * FROM <table> LIMIT 1"`.

| source | when | how it reaches PostHog | extra cost |
|---|---|---|---|
| `stripe` (usual for web billing) | web checkout on Stripe | Stripe data warehouse source; PostHog revenue analytics on top | none beyond Stripe's fees |
| `revenuecat` | mobile in-app subscriptions, or mobile plus web | RevenueCat data warehouse source; HogQL over its tables | RevenueCat's own pricing (free to $2,500 tracked revenue a month, then 1%; verify) |
| `paddle` · `chargebee` · `polar` | those billing platforms | their data warehouse sources; HogQL | none |
| `events` | own billing or a license server | the product sends revenue events | none |

## stripe

1. In PostHog, add Stripe as a data warehouse source with a restricted Stripe key. PostHog
   recommends giving the key write access to webhooks so it can set up webhook syncing, which keeps
   changes to existing rows (cancellations, refunds) accurate. Follow PostHog's Stripe source page
   for the exact permissions.
2. Turn on revenue analytics. It computes MRR (new, expansion, contraction, churn), gross revenue,
   customers, ARPU and LTV from the synced data.
3. Add the queries the rungs read. Shapes to adapt after checking the schema (verify):

   ```json
   "queries": {
     "churn_rate_monthly": "SELECT … churned MRR last month / MRR at the start of last month …",
     "nrr": "SELECT … MRR now from customers who paid a year ago / their MRR a year ago …"
   },
   "query_tracks": {"churn_rate_monthly": "retention", "nrr": "retention"}
   ```

   PostHog's revenue analytics exposes its numbers as managed views; query those rather than raw
   Stripe tables when they have what you need, and preview the view's columns first.

Stripe rows count against the warehouse's monthly free rows (1M rows a month on the free plan;
verify).

## revenuecat

Connect RevenueCat as a data warehouse source. PostHog's revenue analytics doesn't read RevenueCat
yet (listed as coming), so write the metrics as HogQL over the imported tables: active
subscriptions, cancellations in the month, revenue by customer. Inspect the tables first; their
names and columns follow RevenueCat's export, not Stripe's. RevenueCat is only worth its fee when the
product sells inside mobile apps: Stripe can't see App Store or Google Play revenue.

## paddle · chargebee · polar

Same pattern as RevenueCat: connect the data warehouse source, inspect the tables, write HogQL for
the metrics, verify each query returns one number. Move to revenue analytics when PostHog supports
the source there.

## events (own billing or a license server)

The product's billing or license code sends the revenue events itself. The agent opens a PR that adds
the capture call where a purchase, renewal or refund is recorded. Use PostHog's server SDK for the
language (`posthog-node`, `posthog` for Python). The project API key is enough; it can only send.

Node (`posthog-node`):

```js
import { PostHog } from "posthog-node";
const posthog = new PostHog(process.env.POSTHOG_PROJECT_API_KEY, { host: "https://us.i.posthog.com" });

// after the payment or license activation is recorded
posthog.capture({
  distinctId: user.id,                 // the same id the app passes to identify()
  event: "purchase",                   // or "renewal", "refund" (negative revenue)
  properties: { revenue: 99.0, currency: "USD", plan: "pro" },
});
await posthog.shutdown();              // flush before a short-lived process exits
```

Python (`posthog`):

```python
from posthog import Posthog
posthog = Posthog(os.environ["POSTHOG_PROJECT_API_KEY"], host="https://us.i.posthog.com")

posthog.capture(distinct_id=user_id, event="purchase",
                properties={"revenue": 99.0, "currency": "USD", "plan": "pro"})
posthog.flush()
```

SDK call signatures change between major versions; check the SDK's README for the installed version
(verify).

**Joining revenue to the funnel.** Revenue only lands at the end of the funnel if it is sent to the
same PostHog person as the visitor:

- Online purchases: use the product's user id, which the app already passes to `identify`.
- Offline license keys (a key bought or emailed, activated later in a desktop app): send the purchase
  with the license id as the `distinctId` (never an email: even hashed it is personal data; a hashed email is a last resort that needs privacy sign-off). When the app first activates the key, call
  `alias` (or `identify` with the license id as an alias, per the SDK) to join that id to the app's
  person. Use a hashed email if the raw address would otherwise appear as an id.

Then the metrics:

```json
"queries": {
  "revenue_28d": "SELECT sum(toFloat(properties.revenue)) FROM events WHERE event IN ('purchase', 'renewal', 'refund') AND timestamp > now() - INTERVAL 28 DAY"
}
```

and `stage_events` can point the paying stage at `purchase`.
