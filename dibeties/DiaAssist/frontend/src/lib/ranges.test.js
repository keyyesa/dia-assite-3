import test from 'node:test'
import assert from 'node:assert/strict'
import { tone, position, segmentWidths, summarize, suggestSpecialities, initials, SCALES } from './ranges.js'

test('tone maps API classifications', () => {
  assert.equal(tone('normal'), 'good')
  assert.equal(tone('prediabetes_range'), 'warn')
  assert.equal(tone('diabetes_range'), 'bad')
  assert.equal(tone('macroalbuminuria'), 'bad')
  assert.equal(tone('unit_not_supported'), 'neutral')
})

test('position is clamped and proportional', () => {
  assert.equal(position('HbA1c', 7), 50)
  assert.equal(position('HbA1c', 1), 0)
  assert.equal(position('HbA1c', 99), 100)
  assert.equal(position('Nope', 5), null)
  assert.equal(position('HbA1c', 'x'), null)
})

test('segment widths add up to 100 for every parameter', () => {
  for (const k of Object.keys(SCALES)) {
    const total = segmentWidths(k).reduce((s, x) => s + x.width, 0)
    assert.ok(Math.abs(total - 100) < 1e-9, k)
  }
})

test('summary and speciality suggestions', () => {
  const v = { HbA1c: { classification: 'diabetes_range' }, LDL: { classification: 'optimal' }, Urine_Albumin: { classification: 'microalbuminuria' } }
  assert.deepEqual(summarize(v), { total: 3, good: 1, attention: 2 })
  assert.deepEqual(suggestSpecialities(v), ['Kidney care', 'Endocrinology'])
  assert.deepEqual(suggestSpecialities({ LDL: { classification: 'optimal' } }), [])
})

test('initials', () => {
  assert.equal(initials('Dr. Sana Malik'), 'SM')
  assert.equal(initials('Ali'), 'A')
  assert.equal(initials(''), '?')
})
