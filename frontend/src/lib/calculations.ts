/**
 * Client-side BBS calculations (mirrors backend logic for instant UI feedback).
 */

const UNIT_WEIGHTS: Record<number, number> = {
  6: 0.222, 8: 0.395, 10: 0.617, 12: 0.888,
  16: 1.578, 20: 2.466, 25: 3.853, 32: 6.313,
};

export function calcCuttingLength(
  shape: string,
  clearLengthM: number,
  diameterMm: number,
  hookLengthMm = 0,
  coverMm = 50
): number {
  const clearMm = clearLengthM * 1000;
  const bendDeduction = 2 * diameterMm;

  let length: number;
  switch (shape) {
    case "STRAIGHT":
      length = clearMm + 2 * coverMm;
      break;
    case "L_SHAPE":
      length = clearMm * 2 - bendDeduction + 2 * coverMm;
      break;
    case "U_SHAPE":
      length = clearMm * 2 + hookLengthMm - bendDeduction + 2 * coverMm;
      break;
    case "HOOK":
      length = clearMm + hookLengthMm + 2 * coverMm;
      break;
    case "SPIRAL":
      length = clearMm * 2 - 4 * diameterMm;
      break;
    default:
      length = clearMm;
  }
  return Math.round((length / 1000) * 1000) / 1000;
}

export function calcWeight(diameterMm: number, lengthM: number): number {
  const uw = UNIT_WEIGHTS[diameterMm] ?? 0;
  return Math.round(lengthM * uw * 1000) / 1000;
}

// ── Laps ────────────────────────────────────────────────────────────────────
// Preview-only mirror of backend/app/utils/concrete_grades.py. The API is the
// authority: the saved bar carries design_code + citation from the server.
// Keep this in sync — the parity values are asserted in
// backend/tests/test_concrete_grades.py.

export const STANDARD_EC2 = "ES_EN_1992_1_1";
export const STANDARD_EBCS_2 = "EBCS_2";

/** Default design grade when the bar does not name one. */
export const DEFAULT_GRADE = "C25/30";

export type GradeConvention = "CUBE" | "CYLINDER";

/** EN 206 / ES EN 206 standard classes as [f_ck,cyl, f_cu,cube]. */
export const STANDARD_GRADE_PAIRS: ReadonlyArray<readonly [number, number]> = [
  [12, 15], [16, 20], [20, 25], [25, 30], [30, 37],
  [35, 45], [40, 50], [45, 55], [50, 60],
];

export interface ConcreteGrade {
  fckCyl: number;   // f_ck,cyl (MPa)
  fcuCube: number;  // f_cu      (MPa)
  convention: GradeConvention;
  rateKey: string;
}

/**
 * Parse an Ethiopian concrete grade. "C25/30" is unambiguous (cylinder/cube).
 * "C-25" is not: under EBCS-2 it means f_cu = 25 (cube), under EC2 it means
 * f_ck,cyl = 25 (cylinder). Those are different mixes — see
 * docs/USER_GUIDE.md § Concrete grade conventions.
 */
export function parseGrade(text: string, standard = STANDARD_EC2): ConcreteGrade {
  const cleaned = text.trim().replace(/\s+/g, "");
  const pair = cleaned.match(/^[Cc]-?(\d{2})\/(\d{2})$/);
  if (pair) {
    const fck = Number(pair[1]);
    const fcu = Number(pair[2]);
    return { fckCyl: fck, fcuCube: fcu, convention: "CYLINDER", rateKey: `C${fck}/${fcu}` };
  }
  const single = cleaned.match(/^[Cc]-?(\d{2})$/);
  if (!single) throw new Error(`Unrecognised concrete grade: ${text}`);
  const value = Number(single[1]);
  const isCube = standard === STANDARD_EBCS_2;
  const fck = isCube ? value * 0.8 : value;
  const fcu = isCube ? value : value / 0.8;
  // A derived pair like C25/31.25 is not a mix anyone sells; snap to the
  // nearest EN 206 class, exactly as the backend does.
  const snap = STANDARD_GRADE_PAIRS.reduce<{ d: number; pair: readonly [number, number] } | null>(
    (best, pair) => {
      const [pc, pu] = pair;
      if (Math.abs(pu - fcu) > 3) return best;
      const d = Math.abs(pc - fck) + Math.abs(pu - fcu);
      return best === null || d < best.d ? { d, pair } : best;
    },
    null,
  );
  const rateKey = snap ? `C${snap.pair[0]}/${snap.pair[1]}` : `C${round1(fck)}/${round1(fcu)}`;
  return {
    fckCyl: round1(fck),
    fcuCube: round1(fcu),
    convention: isCube ? "CUBE" : "CYLINDER",
    rateKey,
  };
}

function round1(n: number): number {
  return Math.round(n * 100) / 100;
}

/**
 * Mean tensile strength, EC2 Table 3.1: f_ctm = 0.30 * f_ck^(2/3) (f_ck <= 50).
 */
export function calcFctm(fckCyl: number): number {
  if (fckCyl <= 50) return 0.3 * Math.pow(fckCyl, 2 / 3);
  return 2.12 * Math.log(1 + (fckCyl + 8) / 10);
}

export interface LapOptions {
  steelFykMpa?: number;
  gammaC?: number;
  gammaS?: number;
  staggered?: boolean;
}

/**
 * Design lap length l_0 per ES EN 1992-1-1:2015 §8.4.4 (returns mm).
 *
 *   f_ctd    = f_ctk,0.05 / gamma_c ,  f_ctk,0.05 = 0.7 * f_ctm
 *   f_bd     = 2.25 * eta1 * eta2 * f_ctd
 *   l_b,rqd  = (phi/4) * (f_yk/gamma_s) / f_bd
 *   l_0      = a1*a2*a3*a5*a6 * l_b,rqd   (a6 = 1.5 lapped / 1.4 staggered)
 *   l_0     >= max(0.3*a6*l_b,rqd, 15*phi, 200)
 */
export function calcLapLengthEc2(
  diameterMm: number,
  grade: ConcreteGrade,
  opts: LapOptions = {},
): number {
  const { steelFykMpa = 500, gammaC = 1.5, gammaS = 1.15, staggered = false } = opts;
  const alpha6 = staggered ? 1.4 : 1.5;
  const eta2 = diameterMm <= 32 ? 1.0 : 0.7;

  const fctm = calcFctm(grade.fckCyl);
  const fctd = (0.7 * fctm) / gammaC;
  const fbd = 2.25 * 1.0 * eta2 * fctd;
  const sigmaSd = steelFykMpa / gammaS;

  const lbRqd = (diameterMm / 4) * (sigmaSd / fbd);
  const l0 = alpha6 * lbRqd;
  const l0Min = Math.max(0.3 * alpha6 * lbRqd, 15 * diameterMm, 200);
  return Math.max(l0, l0Min);
}

/**
 * Lap length in mm for the selected code of practice.
 * ES_EN_1992_1_1 -> EC2 formula. EBCS_2 -> 50*phi site-practice multiple.
 * Legacy "EBCS_3" is accepted (it meant EBCS-2) but never offered in the UI.
 */
export function calcLapLength(
  diameterMm: number,
  standard = STANDARD_EC2,
  concreteGrade: string = DEFAULT_GRADE,
): number {
  const key = standard === "EBCS_3" ? STANDARD_EBCS_2 : standard;
  if (key === STANDARD_EBCS_2) return diameterMm * 50;
  if (key !== STANDARD_EC2) {
    throw new Error(`${standard} does not define lap lengths (use ${STANDARD_EC2})`);
  }
  return Math.round(calcLapLengthEc2(diameterMm, parseGrade(concreteGrade)));
}
