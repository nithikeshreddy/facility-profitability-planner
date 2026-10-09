# Facility Profitability Planner — Product and Build Spec

Save this file in your project folder as `docs/SPEC.md`. Claude Code reads it in Prompt 1.

## 1. Purpose

A prototype for the abrightlab 2,000-Location Challenge. An operations manager can:

> Open a loss-making location → inspect the evidence → compare possible fixes → review costs and feasibility → save a proposed action.

All data is synthetic and must be labeled "Demonstration data" in the UI. The app must stay consistent with the 2-page written submission (summary in section 9).

## 2. Stack (fixed, do not change)

| Part | Technology |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS, React Router, react-leaflet (Leaflet) for the map |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Database | SQLite via SQLAlchemy 2.x |
| Tests | pytest (backend). Optional: Vitest for a couple of frontend utilities |
| Deployment | One service: FastAPI serves `/api/*` and the built frontend from `frontend/dist` |

No live AI or LLM API calls in the app. All explanations are generated from transparent rules and templates. (Automated natural-language explanations are a later phase.)

## 3. Repository layout

```
facility-planner/
  CLAUDE.md
  README.md
  docs/SPEC.md
  backend/
    app/
      main.py            # FastAPI app, mounts API + static frontend
      db.py              # engine, session, Base
      models.py          # SQLAlchemy models
      schemas.py         # Pydantic response/request models
      seed.py            # deterministic synthetic data (12 detailed + ~2,000 lightweight)
      rules/
        finance.py       # contribution, reasonable-cost range
        diagnosis.py     # root-cause flags with evidence
        feasibility.py   # service window, travel, crew capacity checks
        bundles.py       # nearby + compatible grouping, bundle evaluation
        renewals.py      # renewal queue
        incentives.py    # bonus eligibility and cost
      routers/           # one router per area
    tests/
    requirements.txt
  frontend/
    src/ (pages, components, api client, types)
```

## 4. Core formulas (all monthly, USD)

- **Contribution** = revenue − vendor invoices − other direct costs − company-paid return visits − customer credits − vendor bonuses.
- Estimated labor and travel only *explain* an invoice; they are never added on top of an actual invoice.
- **Reasonable-cost range** (estimate) per location:
  - crew_minutes_per_visit = Σ(task minutes from site profile) ; visits_per_month = frequency × 4.33
  - labor = crew_minutes_per_visit / 60 × visits_per_month × local_loaded_wage
  - travel = travel_minutes_per_visit / 60 × visits_per_month × local_loaded_wage
  - supplies = supplies_per_visit × visits_per_month
  - range low = (labor + travel + supplies) × (1 + 0.15 margin); range high = same × (1 + 0.25 margin)
  - Every assumption (wage, margin band, supplies) is stored, labeled, and shown in the UI.
- **Diagnosis split** (from the submission):
  - actual cost > estimate high → **delivery problem** (fix how work is delivered)
  - estimate low > revenue → **pricing/scope problem** (send to renewal review)
  - both can be true; show both.
- **Plan evaluation**: projected contribution = revenue − projected vendor cost − projected other costs − bonus (full cap assumed, only if that vendor has a bonus program) − transition cost amortized over 12 months. A plan is only recommended if it is feasible AND projected contribution beats current.
- **Feasibility**: for each site in a plan, (cleaning minutes ÷ crew size) + travel minutes from previous stop must fit inside the site's service window; total crew-hours per night must not exceed the vendor's available crews × shift length. Failure returns a plain-English reason, e.g. *"This offer is cheaper, but its crew requires 225 minutes within a 180-minute service window."*
- **Incentives**: bonus = min(bonus_rate × monthly invoice, cap) only when ALL targets are met; failures marked customer-caused are excluded from the calculation; anything excluded is listed for exception review.
- **Renewal queue**: contracts where estimate low > revenue, or still loss-making after the best feasible plan; sorted by renewal date, then by monthly gap. Suggest price, scope, or frequency review with the price needed to reach a target margin (default 10%).

Every money figure carries a **kind**: `estimated`, `quoted`, or `actual`, shown in the UI as a small badge.

## 5. Data model (minimum)

- `Vendor`: id, name, home_base lat/lng, crews_available, shift_minutes, bonus_rate, bonus_cap
- `Location`: id, name, city, state, lat, lng, detailed (bool), customer_account, revenue_monthly, sq_ft, restrooms, floors, building_type, service_window_start, service_window_end, frequency_per_week, current_vendor_id, local_loaded_wage
- `Contract`: location_id, price_monthly, scope (text list), frequency_per_week, start_date, renewal_date
- `Invoice`: location_id, vendor_id, month, amount, kind (`actual`), line_type (`base`, `return_visit`, `extra`)
- `CostItem`: location_id, month, type (`credit`, `other_direct`, `bonus`), amount
- `ServiceVisit`: location_id, date, checkin, checkout, completed (bool), return_visit (bool)
- `IssueRecord`: location_id, date, category (`access`, `quality`, `scope`, `missed`), description, customer_caused (bool), resolved_hours
- `Inspection`: location_id, date, score (0–100)
- `VendorOffer`: id, vendor_id, location_ids (bundle), monthly_price (quoted), crew_size, minutes_per_site, transition_cost_one_time
- `PerformanceTarget`: vendor_id, completion_min, inspection_avg_min, fix_within_24h_min
- `ProposedAction`: id, location_id, plan_type, summary, projected_contribution, status (`proposed`), created_at, note
- Lightweight sites (~2,000): `Location` rows with `detailed=false` and only summary fields (revenue, actual cost this month, lat/lng, city). No visits/issues.

## 6. Demonstration data

Deterministic (fixed random seed). 4 vendors, 12 detailed locations, ~2,000 lightweight sites spread across real U.S. metro coordinates, roughly 10–15% loss-making.

The 12 detailed locations must include these five cases. Numbers below are the targets; seed data and tests must reproduce them from the records, not hardcode results.

1. **Suitable bundle (Dallas, 3 sites within ~5 miles).** Each earns $1,100/mo and costs $1,250/mo actual from two different current vendors, each driving out separately (travel-heavy). Vendor "Metro Clean Co" quotes $3,150/mo for all three on one route, transition cost $300 one-time ($25/mo across the bundle when amortized over 12 months). Metro Clean Co has no bonus program. Route fits each site's window. Expected: bundle is feasible and each site's contribution goes from −$150 to roughly +$42.
2. **Operational fix (Phoenix).** Revenue $1,500. Base invoice $1,380 plus 4 company-paid return visits at $95 ($380) in the last month because the stockroom was locked (4 `access` issue records, with evidence dates). Contribution −$260. Fix: install lockbox ($150 one-time), expected to remove ~90% of return visits, no vendor change. Projected contribution ≈ +$70.
3. **Underpriced agreement (Columbus).** Revenue $900. Actual cost $1,240. Reasonable-cost estimate ≈ $1,150–$1,300 (labeled assumptions). Estimate exceeds revenue, so no vendor change can fix it → appears in Renewal review with renewal date ~45 days out and a suggested price.
4. **Infeasible cheap offer (Atlanta).** Service window 22:00–01:00 (180 min). Current vendor: crew of 2, cost $1,300. "Budget Shine" offers $1,050 with a crew of 1 needing 225 minutes. Offer is rejected with the reason sentence above.
5. **Performance bonus (Denver).** Revenue $1,600, invoice $1,350. Vendor targets: completion ≥ 98%, inspection average ≥ 90, issues fixed within 24h ≥ 90%. Bonus 5% of invoice capped at $75 → $67.50, contribution $182.50. Changing one inspection to below target (or un-marking a customer-caused failure) makes the vendor ineligible and contribution updates.

The other 7 detailed locations: a mix of healthy and mildly loss-making sites, at least one with missing evidence (e.g. no inspections recorded) so the UI shows "Evidence missing" rather than guessing.

## 7. Screens

All share one layout: left nav, a "Demonstration data" banner, and a **Reset demo** button.

1. **Overview** — KPI tiles (revenue, direct costs, contribution, # loss-making), Leaflet map of all ~2,000 sites (canvas rendering, red = loss, green = profit), filters (state, loss-only, detailed-only), a sortable table; click a detailed site to open it.
2. **Location details** — contract and service requirements, contribution waterfall, reasonable-cost range vs actual vs revenue, diagnosis flags each with its evidence records, missing-evidence warnings.
3. **Compare plans** — current vs operational fix vs vendor offers/bundles side by side; editable assumptions (wage, margin, return-visit reduction %, transition amortization months) that re-run the calculation via the API; feasibility pass/fail with reasons; **Save proposed action**.
4. **Renewal review** — queue sorted by renewal date and gap, suggested price/scope/frequency review.
5. **Vendor incentives** — per vendor targets vs results, eligibility, bonus amount, contribution after bonus, exception list; a toggle to change one service result and see eligibility change.

## 8. Build order

1. Data model, seed, rules, unit tests.
2. Backend API and one end-to-end workflow (open location → evaluate plans → feasibility).
3. Frontend: Overview + map, Location details, Compare plans (features 1–3 complete end to end first).
4. Renewal review, then Vendor incentives.
5. Tests for key cases, polish, single-service build, README, deploy.

Out of scope: live Peazy integration, payments, auth, nationwide route optimizer, live AI.

## 9. Consistency with the written submission

The submission frames a loop: find the loss, prove its cause, apply the matching fix, keep only changes confirmed by invoices. Use its language in the UI: contribution, reasonable cost, delivery problem vs pricing/scope problem, operational fix, vendor bundle, renewal review, vendor incentives, managers approve every change. Savings are labeled "projected" until invoices confirm them.
