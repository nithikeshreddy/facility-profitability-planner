# Facility Profitability Planner

A working prototype for the **abrightlab 2,000-Location Challenge**: a facility-services company holds about 2,000 cleaning contracts, and some of them lose money. The challenge asks how an operations team should find those losses and fix them. This app shows the answer from the written submission as one workflow an operations manager can click through:

> Open a loss-making location → inspect the evidence → compare possible fixes → review costs and feasibility → save a proposed action.

The underlying loop: **find the loss, prove its cause, apply the matching fix, and keep only changes confirmed by invoices.** Savings stay labeled *projected* until invoices confirm them, and managers approve every change. The challenge framing and product spec are in [docs/SPEC.md](docs/SPEC.md) ([§1 Purpose](docs/SPEC.md#1-purpose), [§9 Consistency with the written submission](docs/SPEC.md#9-consistency-with-the-written-submission)).

**All data is synthetic** demonstration data. It is deterministic and generated from a fixed seed: 4 vendors, 12 detailed locations and about 2,000 summary-only sites across real U.S. metros, roughly 13% of them loss-making.

## Live demo

**https://facility-planner.onrender.com** 

It runs on Render's free plan, so the instance sleeps when idle and the first request can take up to a minute to wake it. Each wake starts from freshly seeded demonstration data, so saved proposed actions do not survive a restart.

## Screens

| Screen | Path | What it shows |
|---|---|---|
| Overview | `/` | KPI tiles (revenue, direct costs, contribution, loss-making count), a map of all ~2,000 sites (red = loss, green = profit), filters and a sortable table |
| Location details | `/locations/:id` | Contract and service requirements, contribution waterfall, reasonable-cost range vs actual vs revenue, diagnosis flags with their evidence records, missing-evidence warnings, saved proposed actions |
| Compare plans | `/compare?location=:id` | Current delivery vs operational fix vs vendor offers and bundles; editable assumptions re-run on the server; feasibility pass/fail with reasons; **Save proposed action** |
| Renewal review | `/renewals` | Contracts to reprice or re-scope, sorted by renewal date then monthly gap, with a suggested price and frequency/scope review |
| Vendor incentives | `/incentives` | Targets vs results per vendor, eligibility, bonus, contribution after bonus, exceptions; simulate one changed service result |
| About this demo | `/about` | The method, the settled interpretations, and links to each demo case |

Every page carries the "Demonstration data" banner and a **Reset demo** button. Every money value carries a badge saying where it comes from: **actual** (invoices or recorded costs), **estimated** (calculated from labeled assumptions, including projections) or **quoted** (a vendor offer).

## The five demo cases

The seed data reproduces these from records; no result is hardcoded. IDs are stable because the seed is deterministic, and the **About this demo** page resolves them by location code.

| # | Case | Where to see it | What you should see |
|---|---|---|---|
| 1 | **Suitable vendor bundle** — 3 Dallas sites within ~5 mi, served by two vendors driving out separately | [Compare plans → Dallas Uptown](https://facility-planner.onrender.com/compare?location=1) (`DAL-01`, also `DAL-02`/`DAL-03`) | Metro Clean Co's bundle ($3,150/mo for three, $300 transition) is feasible; each site goes from −$150 to about +$42 projected |
| 2 | **Operational fix** — Phoenix, return visits caused by a locked stockroom | [Location details](https://facility-planner.onrender.com/locations/4) and [Compare plans](https://facility-planner.onrender.com/compare?location=4) (`PHX-01`) | Contribution −$260 with four dated `access` issues; a $150 lockbox removes ~90% of return visits → about +$70 projected, no vendor change |
| 3 | **Underpriced agreement** — Columbus | [Location details](https://facility-planner.onrender.com/locations/5) and [Renewal review](https://facility-planner.onrender.com/renewals) (`COL-01`) | The reasonable-cost estimate (≈ $1,150–$1,300) exceeds $900 revenue, so it is a pricing/scope problem. Renewal is ~45 days out, with a suggested price of $1,377.78 |
| 4 | **Infeasible cheap offer** — Atlanta, 22:00–01:00 window | [Compare plans](https://facility-planner.onrender.com/compare?location=6) (`ATL-01`) | Budget Shine's $1,050 offer is rejected: *"This offer is cheaper, but its crew requires 225 minutes within a 180-minute service window."* It cannot be saved |
| 5 | **Performance bonus** — Denver, Summit Janitorial | [Vendor incentives](https://facility-planner.onrender.com/incentives) (`DEN-01`) | Bonus $67.50, contribution $182.50. Lower one inspection below target, or un-mark the customer-caused miss, and the vendor becomes ineligible; contribution updates |

`MSP-01` (Minneapolis, [location details](https://facility-planner.onrender.com/locations/12)) has no inspections recorded, so the app shows **Evidence missing** instead of guessing.

## Formulas and assumptions (all monthly, USD)

- **Contribution** = revenue − vendor invoices − other direct costs − company-paid return visits − customer credits − vendor bonuses. Estimated labor and travel only *explain* an invoice; they are never added on top of it.
- **Reasonable-cost range** (estimated):
  - visits per month = frequency per week × 4.33
  - labor = crew minutes per visit ÷ 60 × visits × local loaded wage
  - travel = travel minutes per visit ÷ 60 × visits × local loaded wage
  - supplies = supplies per visit × visits
  - range = (labor + travel + supplies) × 1.15 to × 1.25

  Every assumption (wage, margin band, supplies) is stored, labeled and shown in the UI, and can be changed in Compare plans.
- **Diagnosis** (both can be true):
  - actual cost > estimate high → **delivery problem** (fix how work is delivered)
  - estimate low > revenue → **pricing/scope problem** (send to renewal review)
- **Plan evaluation**: projected contribution = revenue − projected vendor cost − projected other costs − bonus (full cap, only if the vendor has a bonus program) − transition cost ÷ 12. A plan is recommended only if it is **feasible** *and* beats current contribution.
- **Feasibility**: for each site, (cleaning minutes ÷ crew size) + travel from the previous stop must fit the service window, and total crew time must fit the vendor's crews × shift length. A failed check returns a plain-English reason.
- **Incentives**: bonus = min(rate × monthly invoice, cap), paid only when every target is met. Customer-caused failures are excluded and listed for exception review.
- **Renewal queue**: contracts where estimate low > revenue, or still loss-making after the best feasible plan. Suggested price reaches a 10% target margin.

**Settled interpretations** (each cost is counted once):
1. Invoice lines with `line_type = return_visit` *are* the company-paid return visits. "Vendor invoices" means `base` + `extra` lines only.
2. Contribution uses the bonus computed by the incentive rules. A stored bonus cost item is never added on top.
3. Travel to a route's first stop counts as 0 minutes, because it happens before the window opens.
4. Crew capacity assumes every site in an offer is serviced the same night (worst case).
5. A bundle's quoted price and amortized transition cost are split equally across its sites.
6. Vendor changes keep current return visits; only an operational fix reduces them.
7. Suggested renewal price = max(cost after the best feasible plan, reasonable-cost low) ÷ (1 − target margin).

The rules live in [backend/app/rules/](backend/app/rules/) as pure functions with pytest tests.

## Run locally

Prerequisites: Python 3.11+ and Node 20.19+ (or 22.12+).

### Development (two processes, hot reload)

```bash
# Backend: FastAPI on :8000
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend: Vite on :5173, proxies /api → :8000
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Single service (how it is deployed)

```bash
./build.sh   # npm ci + vite build → frontend/dist; creates backend/.venv and installs requirements
./start.sh   # uvicorn on 0.0.0.0:$PORT (default 8000)
```

Open http://localhost:8000. FastAPI serves `/api/*` and the built frontend. Any other path that is not a real file returns `index.html`, so direct links like `/compare?location=1` work. Unknown `/api/*` paths return a JSON 404. API docs are at `/docs`.

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | `8000` | Port to listen on |
| `DATABASE_PATH` | `backend/facility.db` | SQLite file. If missing or empty at startup, it is seeded with the demonstration data |
| `DATABASE_URL` | — | Full SQLAlchemy URL; overrides `DATABASE_PATH` (tests use in-memory `sqlite://`) |
| `PYTHON` | `python3.11` | Interpreter `build.sh` uses to create the venv |

The service runs a single worker on purpose: SQLite, seed-on-startup and one shared demo state.

## Docker

Multi-stage image: a Node build stage, then a slim Python runtime running as a non-root user.

```bash
docker build -t facility-planner .
docker run --rm -p 8000:8000 facility-planner                 # http://localhost:8000
docker run --rm -p 9000:9000 -e PORT=9000 facility-planner      # http://localhost:9000
docker run --rm -p 8000:8000 -v fp-data:/data facility-planner # keep the database across restarts
```

The database lives at `/data/facility.db` and is seeded on first start.

To deploy on Render, create a Blueprint from this repo: [render.yaml](render.yaml) defines one free Docker web service with `/api/health` as its health check. Render sets `$PORT`, and the container listens on `0.0.0.0:$PORT`.

## Tests and lint

```bash
cd backend && .venv/bin/pytest            # rules, the five demo cases, API workflows, single-service routing
cd frontend && npm run build && npm run lint
```

## Limitations

- **Synthetic data only.** Every location, vendor, invoice and inspection is generated. Nothing reflects a real customer.
- **No live Peazy integration.** Records come from the seed, not from a field-service system.
- **No authentication.** Anyone with the URL can use the app.
- **No route optimizer.** Bundles are pre-defined vendor offers checked for feasibility; there is no nationwide routing.
- **No live AI.** Every explanation is a rule-based template over the calculated numbers.
- **Shared demo state.** All visitors share one database. Saved actions and changes are visible to everyone until someone presses **Reset demo**, which restores the original data.
- Projected savings are estimates. Nothing here confirms them against later invoices.


## AI tools used

Developed with assistance from Claude Code, all business rules and financial calculations are transparent, deterministic, and fully covered by tests.
