// Typed client for the FastAPI backend. Types mirror backend/app/schemas.py.
// Every number shown in the UI comes from these responses; nothing is computed client-side.

export type Kind = 'estimated' | 'quoted' | 'actual'
export type PlanType = 'current' | 'operational_fix' | 'vendor_offer' | 'vendor_bundle'

export interface Money {
  amount: number
  kind: Kind
}

export interface Ref {
  type: string
  id: number
}

export interface Line {
  key: string
  label: string
  money: Money
  evidence: Ref[]
}

export interface Assumption {
  key: string
  label: string
  value: number
  unit: string
  source: string
}

export interface EvidenceItem {
  type: string
  id: number
  date: string | null
  summary: string
  money: Money | null
}

export interface Contribution {
  revenue: Money
  lines: Line[]
  total: Money
  reasons: string[]
}

export interface CostRange {
  available: boolean
  crew_minutes_per_visit: number
  visits_per_month: number
  labor: Money
  travel: Money
  supplies: Money
  base: Money
  low: Money
  high: Money
  assumptions: Assumption[]
  missing: string[]
  reasons: string[]
  evidence: Ref[]
}

// ---------------------------------------------------------------- overview

export interface Totals {
  sites: number
  detailed_sites: number
  loss_making: number
  revenue: Money
  direct_costs: Money
  contribution: Money
}

export interface Site {
  id: number
  code: string
  name: string
  city: string
  state: string
  lat: number
  lng: number
  detailed: boolean
  revenue: Money
  direct_costs: Money
  contribution: Money
}

export interface Overview {
  totals: Totals
  states: string[]
  sites: Site[]
}

export interface OverviewFilters {
  state?: string
  loss_only?: boolean
  detailed_only?: boolean
}

// ---------------------------------------------------------------- location details

export interface LocationInfo {
  id: number
  code: string
  name: string
  city: string
  state: string
  lat: number
  lng: number
  customer_account: string
  building_type: string | null
  sq_ft: number | null
  restrooms: number | null
  floors: number | null
  current_vendor_id: number | null
  current_vendor_name: string | null
}

export interface Contract {
  id: number
  price_monthly: Money
  scope: string[]
  frequency_per_week: number
  start_date: string
  renewal_date: string
  days_to_renewal: number
}

export interface Task {
  id: number
  task: string
  minutes: number
}

export interface ServiceRequirements {
  window_start: string | null
  window_end: string | null
  window_minutes: number | null
  frequency_per_week: number | null
  current_crew_size: number | null
  tasks: Task[]
  crew_minutes_per_visit: number
}

export interface Flag {
  key: string
  label: string
  action: string
  reasons: string[]
  evidence: EvidenceItem[]
}

export interface Diagnosis {
  flags: Flag[]
  reasons: string[]
}

export interface MissingEvidence {
  key: string
  message: string
}

export interface TargetCheck {
  key: string
  label: string
  target: number
  actual: number | null
  met: boolean
  detail: string
  evidence: Ref[]
}

export interface IncentiveException {
  ref: Ref
  reason: string
}

export interface Incentive {
  vendor_id: number
  has_program: boolean
  eligible: boolean
  invoice_basis: Money
  bonus: Money
  checks: TargetCheck[]
  exceptions: IncentiveException[]
  reasons: string[]
}

export interface LocationDetail {
  location: LocationInfo
  contract: Contract | null
  service_requirements: ServiceRequirements
  month: string
  as_of: string
  contribution: Contribution
  reasonable_cost: CostRange
  actual_cleaning_cost: Money
  diagnosis: Diagnosis
  missing_evidence: MissingEvidence[]
  incentive: Incentive
}

// ---------------------------------------------------------------- plans

/** Optional assumption overrides. Ratios are 0–1 (the UI shows them as %). */
export interface PlanOverrides {
  local_loaded_wage?: number | null
  margin_low?: number | null
  margin_high?: number | null
  return_visit_reduction?: number | null
  amortization_months?: number | null
}

export interface SiteCheck {
  location_id: number
  location_name: string
  cleaning_minutes: number
  travel_minutes: number
  required_minutes: number
  window_minutes: number | null
  fits: boolean
  sentence: string
}

export interface Feasibility {
  feasible: boolean
  capacity_ok: boolean
  total_crew_minutes: number
  capacity_minutes: number
  site_checks: SiteCheck[]
  reasons: string[]
}

/** One stop of a vendor bundle: its route check and its own share of the offer. */
export interface BundleSite {
  location_id: number
  location_name: string
  lat: number
  lng: number
  is_this_location: boolean
  fits: boolean
  required_minutes: number
  window_minutes: number | null
  current_contribution: Money
  projected_contribution: Money
  change: Money
}

export interface Plan {
  plan_type: PlanType
  name: string
  location_id: number
  vendor_id: number | null
  vendor_name: string | null
  vendor_change: boolean
  feasible: boolean
  recommended: boolean
  revenue: Money
  lines: Line[]
  /** Vendor cost + other direct costs + return visits + credits. */
  monthly_cost: Money
  bonus: Money
  transition_monthly: Money
  /** Whole fix or whole offer, before amortization. */
  transition_one_time: Money
  projected_contribution: Money
  current_contribution: Money
  change: Money
  offer_id: number | null
  fix_id: number | null
  feasibility: Feasibility | null
  /** Per-site results; bundles only. */
  sites: BundleSite[]
  reasons: string[]
  evidence: Ref[]
}

export interface Recommended {
  plan_type: PlanType
  name: string
  offer_id: number | null
  fix_id: number | null
}

export interface PlanComparison {
  location_id: number
  assumptions: Assumption[]
  reasonable_cost: CostRange
  current: Plan
  options: Plan[]
  recommended: Recommended | null
  recommendation_reasons: string[]
}

// ---------------------------------------------------------------- renewal review

export type RenewalTrigger = 'pricing_scope_problem' | 'loss_after_best_plan'

export interface Suggestion {
  key: 'price_review' | 'frequency_review' | 'scope_review'
  text: string
}

export interface RenewalItem {
  location_id: number
  location_name: string
  contract_id: number
  renewal_date: string
  days_to_renewal: number
  revenue: Money
  estimate_low: Money | null
  estimate_high: Money | null
  actual_cost: Money | null
  cost_basis: Money
  monthly_gap: Money
  suggested_price: Money
  projected_contribution: Money
  target_margin: number
  current_frequency_per_week: number
  suggested_frequency_per_week: number | null
  triggers: RenewalTrigger[]
  suggestions: Suggestion[]
  reasons: string[]
  evidence: Ref[]
}

export interface RenewalQueue {
  as_of: string
  target_margin: number
  items: RenewalItem[]
}

// ---------------------------------------------------------------- vendor incentives

export interface Targets {
  completion_min: number
  inspection_avg_min: number
  fix_within_24h_min: number
}

export interface InspectionResult {
  id: number
  date: string
  score: number
}

export interface IssueResult {
  id: number
  date: string
  category: string
  description: string
  customer_caused: boolean
  resolved_hours: number | null
  visit_id: number | null
}

export interface VendorLocation {
  location_id: number
  code: string
  name: string
  city: string
  state: string
  incentive: Incentive
  contribution_before_bonus: Money
  /** After the bonus. */
  contribution: Money
  inspections: InspectionResult[]
  issues: IssueResult[]
}

export interface VendorException {
  location_id: number
  location_name: string
  ref: Ref
  reason: string
}

export interface VendorIncentive {
  vendor_id: number
  vendor_name: string
  has_program: boolean
  bonus_rate: number | null
  bonus_cap: Money | null
  targets: Targets | null
  locations: VendorLocation[]
  total_bonus: Money
  total_contribution: Money
  exceptions: VendorException[]
}

export interface VendorIncentives {
  month: string
  vendors: VendorIncentive[]
}

/** Exactly one changed service result. */
export type ResultChange = { inspection_id: number; score: number } | { issue_id: number; customer_caused: boolean }

export interface Simulation {
  vendor_id: number
  vendor_name: string
  location_id: number
  location_name: string
  changes: string[]
  recorded: VendorLocation
  simulated: VendorLocation
  eligibility_changed: boolean
  contribution_change: Money
}

// ---------------------------------------------------------------- proposed actions

export type ActionType = PlanType | 'renewal_review'

export interface ActionIn {
  location_id: number
  plan_type: ActionType
  offer_id?: number | null
  fix_id?: number | null
  overrides?: PlanOverrides | null
  note?: string | null
}

export interface Action {
  id: number
  location_id: number
  location_name: string
  plan_type: string
  summary: string
  projected_contribution: Money
  status: string
  created_at: string
  note: string | null
  offer_id: number | null
  fix_id: number | null
  overrides: Record<string, number> | null
}

export interface ResetResult {
  status: string
  vendors: number
  detailed_locations: number
  locations: number
}

// ---------------------------------------------------------------- client

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI sends `detail` as a string, or as a list of validation errors for 422s. */
function detailMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d as { msg?: string }).msg ?? String(d)).join('; ')
  }
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
  })
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, detailMessage(body, `Request failed (${res.status})`))
  return body as T
}

function query(params: Record<string, string | boolean | number | undefined>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '' && v !== false) q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

export function getOverview(filters: OverviewFilters = {}, signal?: AbortSignal): Promise<Overview> {
  return request(`/api/overview${query({ ...filters })}`, { signal })
}

export function getLocation(id: number, signal?: AbortSignal): Promise<LocationDetail> {
  return request(`/api/locations/${id}`, { signal })
}

export function comparePlans(id: number, overrides?: PlanOverrides, signal?: AbortSignal): Promise<PlanComparison> {
  return request(`/api/locations/${id}/plans`, {
    method: 'POST',
    body: overrides ? JSON.stringify(overrides) : undefined,
    signal,
  })
}

export function getRenewals(signal?: AbortSignal): Promise<RenewalQueue> {
  return request('/api/renewals', { signal })
}

export function getVendorIncentives(signal?: AbortSignal): Promise<VendorIncentives> {
  return request('/api/vendors/incentives', { signal })
}

/** Recalculates eligibility and contribution with one service result changed. Nothing is saved. */
export function simulateIncentive(vendorId: number, change: ResultChange, signal?: AbortSignal): Promise<Simulation> {
  return request(`/api/vendors/${vendorId}/simulate`, { method: 'POST', body: JSON.stringify(change), signal })
}

export function saveAction(action: ActionIn): Promise<Action> {
  return request('/api/actions', { method: 'POST', body: JSON.stringify(action) })
}

export function listActions(locationId?: number, signal?: AbortSignal): Promise<Action[]> {
  return request(`/api/actions${query({ location_id: locationId })}`, { signal })
}

export function resetDemo(): Promise<ResetResult> {
  return request('/api/demo/reset', { method: 'POST' })
}
