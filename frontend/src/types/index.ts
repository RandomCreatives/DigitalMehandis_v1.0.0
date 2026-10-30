// ── Auth ──────────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  organization: string | null;
  role: "QS_PROFESSIONAL" | "STUDENT" | "CONTRACTOR" | "ADMIN";
  preferred_language: "EN" | "AM";
  email_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ── Projects ──────────────────────────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  location: string;
  description: string | null;
  code_of_practice: string | null;
  unit_system: "METRIC" | "IMPERIAL";
  currency: string;
  scale: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  location: string;
  description?: string;
  code_of_practice?: string;
  unit_system?: string;
  currency?: string;
}

// ── Drawings ──────────────────────────────────────────────────────────────────
export type DrawingCategory = "ARCHITECTURAL" | "STRUCTURAL" | "ELECTRICAL" | "SANITARY";

export interface Drawing {
  id: string;
  project_id: string;
  filename: string;
  file_size_mb: number | null;
  category: DrawingCategory | null;
  page_count: number | null;
  scale: string | null;
  user_notes: string | null;
  uploaded_at: string;
}

// ── Takeoff ───────────────────────────────────────────────────────────────────
export type Section = "SUBSTRUCTURE" | "SUPERSTRUCTURE";

export interface TakeoffItem {
  id: string;
  project_id: string;
  item_code: string | null;
  description: string;
  unit: string;
  quantity: number;
  section: Section | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TakeoffItemCreate {
  description: string;
  unit: string;
  quantity: number;
  section?: Section;
  notes?: string;
}

// ── BBS ───────────────────────────────────────────────────────────────────────
export type BarShape = "STRAIGHT" | "L_SHAPE" | "HOOK" | "U_SHAPE" | "SPIRAL";

export interface BBSBar {
  id: string;
  project_id: string;
  bar_mark: string | null;
  member_name: string;
  bar_diameter_mm: number;
  bar_shape: BarShape;
  quantity: number;
  clear_length_m: number;
  hook_length_mm: number;
  cover_top_mm: number;
  cover_bottom_mm: number;
  lap_length_mm: number | null;
  /** Which code produced lap_length_mm, and its citation (audit trail). */
  design_code?: string | null;
  design_code_title?: string | null;
  citation?: string | null;
  concrete_grade?: string | null;
  cutting_length_m: number | null;
  weight_per_unit_kg: number | null;
  total_weight_kg: number | null;
  section: Section | null;
  notes: string | null;
  created_at: string;
}

export interface BBSBarCreate {
  member_name: string;
  bar_diameter_mm: number;
  bar_shape: BarShape;
  quantity: number;
  clear_length_m: number;
  hook_length_mm?: number;
  cover_top_mm?: number;
  cover_bottom_mm?: number;
  section?: Section;
  notes?: string;
  /** Code of practice for laps: ES_EN_1992_1_1 (default) or EBCS_2. */
  standard?: string;
  /** Concrete grade as written on the BoQ/drawing, e.g. "C25/30" or "C-25". */
  concrete_grade?: string;
}

export interface CuttingListItem {
  diameter_mm: number;
  cutting_length_m: number;
  total_qty: number;
  total_weight_kg: number;
}

// ── BOQ ───────────────────────────────────────────────────────────────────────
export interface BOQLine {
  item_number: number;
  description: string;
  unit: string;
  quantity: number;
  rate: number;
  amount: number;
  notes: string;
}

export interface BOQResult {
  project_id: string;
  section: string;
  lines: BOQLine[];
  total_amount: number;
  currency: string;
}

export interface Rate {
  id: string;
  item_code: string | null;
  description: string;
  unit: string;
  rate_per_unit: number;
  rate_source: string | null;
  region: string | null;
}

// ── Cost Library ─────────────────────────────────────────────────────────────
export interface RateSourceOut {
  id: string;
  title: string;
  issuing_authority: string | null;
  region: string | null;
  fiscal_year: string | null;
  quarter: string | null;
  item_count: number;
  created_at: string;
}

export interface RateItemOut {
  id: string;
  rate_source_id: string;
  parent_id: string | null;
  item_no: string | null;
  description: string;
  unit: string;
  direct_cost: number;
  currency: string;
  source_page: number | null;
  confidence: number;
  children?: RateItemOut[];
}
