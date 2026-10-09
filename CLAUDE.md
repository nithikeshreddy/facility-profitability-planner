# CLAUDE.md — Facility Profitability Planner

`docs/SPEC.md` is the source of truth. This file summarizes it; if the two disagree, the spec wins — fix this file.

## Purpose

Prototype for the abrightlab 2,000-Location Challenge. An operations manager can:

> Open a loss-making location → inspect the evidence → compare possible fixes → review costs and feasibility → save a proposed action.

- All data is synthetic and labeled **"Demonstration data"** in the UI.
- Stay consistent with the written submission. Use its language in the UI: *contribution, reasonable cost, delivery problem vs pricing/scope problem, operational fix, vendor bundle, renewal review, vendor incentives, managers approve every change.*
- Savings are labeled **"projected"** until invoices confirm them.

## Working rules

- **Never hardcode results in the UI.** Every number comes from the API, computed from records.
- **Every money value carries a kind:** `estimated`, `quoted`, or `actual` (shown as a small badge in the UI).
- **No live AI calls.** Explanations are rule-based templates.
- **Business rules live in `backend/app/rules/`** as pure functions (no DB/session access) with pytest tests.
- **Run tests after changing any rule:** `cd backend && .venv/bin/pytest`.
- Demo-case targets (below) must be reproduced from seeded records, never hardcoded in code or tests' expected inputs.

## Stack (fixed — do not change)

| Part | Technology |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS (v4, `@tailwindcss/vite`), React Router, react-leaflet (Leaflet) for the map |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Database | SQLite via SQLAlchemy 2.x |
| Tests | pytest (backend). Optional: Vitest for a couple of frontend utilities |
| Deployment | One service: FastAPI serves `/api/*` and the built frontend from `frontend/dist` (non-file paths → `index.html`; unknown `/api/*` → JSON 404). `./build.sh` + `./start.sh` (`$PORT`), or the multi-stage `Dockerfile` |

## Repo layout

```
facility-planner/
  CLAUDE.md  README.md  docs/SPEC.md
  backend/
    app/
      main.py         # FastAPI app: API routers, seed-on-startup if DB empty, SPA fallback for frontend/dist
      db.py           # engine, SessionLocal, Base, get_db (DATABASE_URL, else DATABASE_PATH)
      models.py       # SQLAlchemy models                       (build step 1)
      schemas.py      # Pydantic request/response models         (build step 1)
      seed.py         # deterministic synthetic data             (build step 1)
      rules/          # pure business rules: finance, diagnosis, feasibility,
                      #   bundles, renewals, incentives          (build step 1)
      routers/        # one router per area (health.py exists)
    tests/            # pytest
    requirements.txt  pytest.ini
    facility.db       # SQLite file (git-ignored; DATABASE_PATH or DATABASE_URL override)
  frontend/
    src/
      components/Layout.tsx   # left nav, "Demonstration data" banner, Reset demo
      pages/                  # Overview, LocationDetails, ComparePlans, RenewalReview, VendorIncentives, About
  build.sh  start.sh  Dockerfile  .dockerignore
```

## Core formulas (all monthly, USD)

- **Contribution** = revenue − vendor invoices − other direct costs − company-paid return visits − customer credits − vendor bonuses.
- Estimated labor and travel only *explain* an invoice; never add them on top of an actual invoice.
- **Reasonable-cost range** (kind `estimated`):
  - `crew_minutes_per_visit = Σ task minutes (site profile)`; `visits_per_month = frequency_per_week × 4.33`
  - `labor = crew_minutes_per_visit / 60 × visits_per_month × local_loaded_wage`
  - `travel = travel_minutes_per_visit / 60 × visits_per_month × local_loaded_wage`
  - `supplies = supplies_per_visit × visits_per_month`
  - `low = (labor + travel + supplies) × 1.15`; `high = (labor + travel + supplies) × 1.25`
  - Every assumption (wage, margin band, supplies) is stored, labeled, and shown in the UI.
- **Diagnosis split** (both can be true — show both):
  - actual cost > estimate high → **delivery problem** (fix how work is delivered)
  - estimate low > revenue → **pricing/scope problem** (send to renewal review)
- **Plan evaluation**: projected contribution = revenue − projected vendor cost − projected other costs − bonus (full cap assumed, only if that vendor has a bonus program) − transition cost ÷ 12. Recommend a plan only if it is **feasible AND** beats current contribution.
- **Feasibility**: per site, `(cleaning minutes ÷ crew size) + travel minutes from previous stop ≤ service window`; total crew-hours per night ≤ vendor `crews_available × shift_minutes`. Failure returns a plain-English reason, e.g. *"This offer is cheaper, but its crew requires 225 minutes within a 180-minute service window."*
- **Incentives**: bonus = `min(bonus_rate × monthly invoice, cap)` only when ALL targets are met; failures marked `customer_caused` are excluded from the calculation; anything excluded is listed for exception review.
- **Renewal queue**: contracts where estimate low > revenue, or still loss-making after the best feasible plan; sorted by renewal date, then monthly gap. Suggest price/scope/frequency review with the price needed to reach a target margin (default 10%).

### Spec interpretation notes (count each cost once)

- **Return visits:** `Invoice` lines with `line_type=return_visit` *are* the company-paid return visits. "Vendor invoices" in the contribution formula = `base` + `extra` lines. (Phoenix: $1,500 − $1,380 − $380 = −$260 only works this way.)
- **Bonus:** contribution uses the bonus computed by `rules/incentives.py` (so the Denver toggle changes contribution). Stored `CostItem(type=bonus)` rows must not be added on top of it.
- **First stop:** feasibility counts travel to a route's first stop as 0 (it happens before the window opens).
- **Capacity:** all sites in an offer are assumed serviced the same night (worst case) for `crews × shift`.
- **Bundle split:** quoted price and amortized transition cost are split equally across the bundle's sites.
- **Vendor changes keep return visits:** only an operational fix reduces company-paid return visits.
- **Renewal price** = `max(cost after best feasible plan, estimate low) ÷ (1 − target margin)` (÷ 0.9 by default).

## Five demo cases (targets to reproduce from records)

| # | Case | Key inputs | Expected |
|---|---|---|---|
| 1 | **Suitable bundle** (Dallas, 3 sites ≤ ~5 mi) | Each: revenue $1,100, actual $1,250 from two different current vendors (travel-heavy). "Metro Clean Co" quotes $3,150/mo for all three, transition $300 one-time ($25/mo amortized across bundle). No bonus program. Route fits each window. | Feasible; each site −$150 → ≈ **+$42** |
| 2 | **Operational fix** (Phoenix) | Revenue $1,500; base invoice $1,380 + 4 return visits × $95 = $380 (4 `access` issues, stockroom locked, with dates). | Current **−$260**. Lockbox $150 one-time, removes ~90% of return visits, no vendor change → ≈ **+$70** |
| 3 | **Underpriced agreement** (Columbus) | Revenue $900; actual $1,240; reasonable-cost estimate ≈ $1,150–$1,300. | Estimate > revenue → no vendor fix; in **Renewal review**, renewal ~45 days out, suggested price |
| 4 | **Infeasible cheap offer** (Atlanta) | Window 22:00–01:00 (180 min). Current crew of 2, $1,300. "Budget Shine" $1,050, crew of 1 needing 225 min. | **Rejected** with the reason sentence above |
| 5 | **Performance bonus** (Denver) | Revenue $1,600, invoice $1,350. Targets: completion ≥ 98%, inspection avg ≥ 90, fixed within 24h ≥ 90%. Bonus 5% capped at $75. | Bonus **$67.50**, contribution **$182.50**. One inspection below target (or un-marking a customer-caused failure) → ineligible, contribution updates |

Other 5 detailed locations: mix of healthy and mildly loss-making; at least one with missing evidence (e.g. no inspections) so the UI shows **"Evidence missing"** rather than guessing.

Data: deterministic (fixed seed), 4 vendors, 12 detailed + ~2,000 lightweight sites (`detailed=false`, summary fields only) across real U.S. metros, ~10–15% loss-making.

## Screens

Shared layout: left nav, "Demonstration data" banner, **Reset demo** button.

1. **Overview** (`/`) — KPI tiles, Leaflet canvas map of all sites (red loss / green profit), filters, sortable table.
2. **Location details** (`/locations`) — contract, contribution waterfall, reasonable-cost range vs actual vs revenue, diagnosis flags with evidence, missing-evidence warnings.
3. **Compare plans** (`/compare`) — current vs operational fix vs offers/bundles; editable assumptions re-run via API; feasibility with reasons; **Save proposed action**.
4. **Renewal review** (`/renewals`) — queue + suggested price/scope/frequency review.
5. **Vendor incentives** (`/incentives`) — targets vs results, eligibility, bonus, exceptions, toggle one service result.
6. **About this demo** (`/about`) — method, settled interpretations, links to each demo case (resolved by location code). Explains formulas only; no computed figures.

## API (`backend/app/routers/`, schemas in `app/schemas.py`)

Routers stay thin: `loaders` (ORM → dataclasses) → `services` (composition) → `rules/` (logic) → Pydantic schema. Money is always `{amount, kind}`.

- `GET  /api/overview?state=&loss_only=&detailed_only=` — KPI totals (over the filtered set), states, compact site list for the map
- `GET  /api/locations/{id}` — contract, service requirements, waterfall, reasonable-cost range + assumptions, diagnosis flags with evidence records, missing evidence, incentive (404 for lightweight sites)
- `POST /api/locations/{id}/plans` — optional overrides `{local_loaded_wage, margin_low, margin_high, return_visit_reduction, amortization_months}` (ratios 0–1; the margin band is checked against the values in effect → 422) → current, operational fixes, offers/bundles with feasibility, card totals (`monthly_cost`, `bonus`, `transition_monthly`, `transition_one_time`), per-site `sites` for bundles, recommended plan + reasons
- `POST /api/actions` — `{location_id, plan_type, offer_id?, fix_id?, overrides?, note?}`; projection recomputed server-side; infeasible plan → 422 with its reason. `plan_type=renewal_review` stores the renewal suggestion (projected = suggested price − cost); 422 if the location is not in the queue or offer/fix/overrides are sent. `GET /api/actions?location_id=`
- `GET  /api/renewals` — renewal queue `{as_of, target_margin, items}`: estimate range, actual cost, gap, renewal date/days, triggers + reasons, suggested price/frequency/scope review
- `GET  /api/vendors/incentives` — per vendor: program, targets, each detailed location served (checks vs targets, bonus, contribution before/after bonus, this month's inspections/issues), exceptions
- `POST /api/vendors/{id}/simulate` — exactly one of `{inspection_id, score}` or `{issue_id, customer_caused}` → `recorded` vs `simulated`; read-only, never writes
- `POST /api/demo/reset` — `reset_and_seed()`

## Build order

1. Data model, seed, rules, unit tests.
2. Backend API and one end-to-end workflow (open location → evaluate plans → feasibility).
3. Frontend: Overview + map, Location details, Compare plans (features 1–3 end to end first).
4. Renewal review, then Vendor incentives.
5. Tests for key cases, polish, single-service build, README, deploy.

Out of scope: live Peazy integration, payments, auth, nationwide route optimizer, live AI.

## Commands

```bash
# Backend (from backend/)
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/pytest

# Frontend (from frontend/) — dev server on :5173, proxies /api → :8000
npm install
npm run dev
npm run build
npm run lint

# Single service (from repo root) — FastAPI serves API + frontend/dist on $PORT
./build.sh && ./start.sh
docker build -t facility-planner . && docker run --rm -p 8000:8000 facility-planner
```
