// Pure helpers (no React) so they can be unit-tested with `node --test`.

// Visual scales for the range bar of every lab value: [from, to, tone]
export const SCALES = {
  HbA1c: { min: 4, max: 10, unit: '%', segs: [[4, 5.7, 'good'], [5.7, 6.5, 'warn'], [6.5, 10, 'bad']] },
  FBG: { min: 50, max: 200, unit: 'mg/dL', segs: [[50, 70, 'warn'], [70, 100, 'good'], [100, 126, 'warn'], [126, 200, 'bad']] },
  RBG: { min: 50, max: 300, unit: 'mg/dL', segs: [[50, 70, 'warn'], [70, 200, 'good'], [200, 300, 'bad']] },
  OGTT_2hr: { min: 60, max: 300, unit: 'mg/dL', segs: [[60, 140, 'good'], [140, 200, 'warn'], [200, 300, 'bad']] },
  Serum_Creatinine: { min: 0.4, max: 3, unit: 'mg/dL', segs: [[0.4, 1.3, 'good'], [1.3, 3, 'bad']] },
  Urine_Albumin: { min: 0, max: 400, unit: 'mg/g', segs: [[0, 30, 'good'], [30, 300, 'warn'], [300, 400, 'bad']] },
  LDL: { min: 40, max: 220, unit: 'mg/dL', segs: [[40, 100, 'good'], [100, 160, 'warn'], [160, 220, 'bad']] },
  HDL: { min: 20, max: 80, unit: 'mg/dL', segs: [[20, 40, 'warn'], [40, 80, 'good']] },
  Triglycerides: { min: 50, max: 500, unit: 'mg/dL', segs: [[50, 150, 'good'], [150, 200, 'warn'], [200, 500, 'bad']] },
}

export const NAMES = {
  HbA1c: 'HbA1c', FBG: 'Fasting glucose', RBG: 'Random glucose', OGTT_2hr: 'OGTT (2 hour)',
  Serum_Creatinine: 'Serum creatinine', Urine_Albumin: 'Urine albumin (UACR)', LDL: 'LDL cholesterol',
  HDL: 'HDL cholesterol', Triglycerides: 'Triglycerides',
}

const GOOD = ['normal', 'optimal', 'acceptable', 'below_diagnostic_threshold']
const WARN = ['low', 'borderline', 'prediabetes_range', 'microalbuminuria']
const NEUTRAL = ['unit_not_supported', 'unknown']

/** 'good' | 'warn' | 'bad' | 'neutral' for a classification label returned by the API. */
export function tone(classification) {
  if (GOOD.includes(classification)) return 'good'
  if (WARN.includes(classification)) return 'warn'
  if (NEUTRAL.includes(classification)) return 'neutral'
  return 'bad'
}

export const pretty = (c) => String(c || '').replaceAll('_', ' ')

/** Marker position 0..100 (% of the bar) for a value, clamped to the scale. */
export function position(param, value) {
  const s = SCALES[param]
  if (!s || !Number.isFinite(Number(value))) return null
  const p = ((Number(value) - s.min) / (s.max - s.min)) * 100
  return Math.min(100, Math.max(0, p))
}

/** Width (%) of each coloured segment of the bar. */
export function segmentWidths(param) {
  const s = SCALES[param]
  if (!s) return []
  return s.segs.map(([a, b, t]) => ({ tone: t, width: ((b - a) / (s.max - s.min)) * 100 }))
}

/** {normal, attention} counts for a result set. */
export function summarize(values) {
  const list = Object.values(values || {})
  const good = list.filter((v) => tone(v.classification) === 'good').length
  return { total: list.length, good, attention: list.length - good }
}

/** Specialities worth suggesting for the abnormal values (first = best match). */
export function suggestSpecialities(values) {
  const bad = (k) => values[k] && tone(values[k].classification) !== 'good'
  const out = []
  if (bad('Serum_Creatinine') || bad('Urine_Albumin')) out.push('Kidney care')
  if (bad('HbA1c') || bad('FBG') || bad('RBG') || bad('OGTT_2hr')) out.push('Endocrinology')
  if (bad('LDL') || bad('Triglycerides') || bad('HDL')) out.push('Nutrition')
  return out
}

/** Initials for an avatar: "Dr. Sana Malik" -> "SM". */
export function initials(name) {
  const parts = String(name || '').replace(/^dr\.?\s+/i, '').trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] || '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export const SAMPLE_REPORT = `Patient Lab Report (De-identified Sample)
Test Date: 2026-01-10

HbA1c: 7.8 %
Fasting Blood Glucose (FBG): 142 mg/dL
Random Blood Glucose (RBG): 210 mg/dL
Serum Creatinine: 1.1 mg/dL
Urine Albumin: 45 mg/g
LDL: 130 mg/dL
HDL: 42 mg/dL
Triglycerides: 180 mg/dL`
