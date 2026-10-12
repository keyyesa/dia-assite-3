// The analysed report is kept for this browser tab only, so it can be attached to a booking.
const KEY = 'diaassist_report'
export function saveReport(values) {
  try { sessionStorage.setItem(KEY, JSON.stringify({ values, at: new Date().toISOString() })) } catch { /* storage blocked */ }
}
export function loadReport() {
  try { const r = JSON.parse(sessionStorage.getItem(KEY) || 'null'); return r && r.values ? r : null } catch { return null }
}
export function clearReport() { try { sessionStorage.removeItem(KEY) } catch { /* ignore */ } }
/** The part of an analysis the API accepts with a booking. */
export const reportForBooking = (values) =>
  Object.fromEntries(Object.entries(values).map(([k, v]) => [k, { value: v.value, unit: v.unit, classification: v.classification }]))
