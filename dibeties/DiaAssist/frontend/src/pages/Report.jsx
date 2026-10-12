import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Err } from '../components.jsx'
import { Icon } from '../icons.jsx'
import { NAMES, SCALES, tone, pretty, position, segmentWidths, summarize, suggestSpecialities, SAMPLE_REPORT } from '../lib/ranges.js'
import { saveReport } from '../lib/report.js'

const TONE_BADGE = { good: 'green', warn: 'amber', bad: 'red', neutral: 'gray' }

function Gauge({ param, value }) {
  const segs = segmentWidths(param)
  const pos = position(param, value)
  if (!segs.length || pos === null) return null
  return (
    <div className="gauge-wrap" aria-hidden="true">
      <div className="gauge">{segs.map((s, i) => <i key={i} className={s.tone} style={{ width: `${s.width}%` }} />)}</div>
      <span className="pin" style={{ left: `${pos}%` }} />
    </div>
  )
}

function LabRow({ param, v }) {
  const t = tone(v.classification)
  const s = SCALES[param]
  return (
    <div className="lab">
      <div className="lab-top">
        <div><div className="lab-name">{NAMES[param] || param}</div>{v.reported_as && <div className="muted">reported as {v.reported_as}</div>}</div>
        <div className="row" style={{ gap: '.7rem' }}>
          <span className="lab-val">{v.value} <small>{v.unit}</small></span>
          <span className={`badge ${TONE_BADGE[t]}`}>{pretty(v.classification)}</span>
        </div>
      </div>
      <Gauge param={param} value={v.value} />
      {s && <div className="row between muted" style={{ fontSize: '.72rem' }}><span>{s.min}</span><span>{s.max}+ {s.unit}</span></div>}
      {v.note && <p className="lab-note">{v.note}</p>}
    </div>
  )
}

export default function Report() {
  const nav = useNavigate()
  const [mode, setMode] = useState('file')
  const [file, setFile] = useState(null)
  const [text, setText] = useState('')
  const [over, setOver] = useState(false)
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [ocr, setOcr] = useState(true)
  const input = useRef(null)

  useEffect(() => { api.get('/health').then((h) => setOcr(h.ocr !== false)).catch(() => {}) }, [])

  const pick = (f) => {
    if (!f) return
    setError('')
    const ok = /\.(pdf|png|jpe?g|txt|docx)$/i.test(f.name)
    if (!ok) { setError('Please choose a PDF, PNG, JPG, TXT or DOCX file.'); return }
    if (f.size > 15 * 1024 * 1024) { setError('This file is larger than 15 MB.'); return }
    setFile(f)
  }
  const analyse = async () => {
    setError(''); setRes(null); setBusy(true)
    try {
      const fd = new FormData()
      if (mode === 'file' && file) fd.append('file', file)
      if (mode === 'text' && text.trim()) fd.append('text', text)
      const r = await api.form('/report/analyze', fd)
      setRes(r)
      if (Object.keys(r.values).length) saveReport(r.values)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const entries = res ? Object.entries(res.values) : []
  const sum = res ? summarize(res.values) : null
  const cats = res ? suggestSpecialities(res.values) : []
  const ready = mode === 'file' ? !!file : !!text.trim()
  const isImage = file && /\.(png|jpe?g)$/i.test(file.name)
  const stage = !res ? 1 : 2

  return (
    <div className="wrap">
      <div className="page-head">
        <h2>Lab report analysis</h2>
        <p>Upload a report and see every value explained against standard ranges.</p>
        <div className="steps" aria-label="Progress">
          <span className={`step ${stage === 1 ? 'on' : 'done'}`}><b>{stage > 1 ? <Icon name="check" size={14} /> : 1}</b>Upload</span>
          <span className={`step ${stage === 2 ? 'on' : ''}`}><b>2</b>Review values</span>
          <span className="step"><b>3</b>Consult a doctor</span>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', alignItems: 'start' }}>
        <div className="card">
          <div className="seg" role="tablist">
            <button role="tab" aria-selected={mode === 'file'} className={mode === 'file' ? 'on' : ''} onClick={() => setMode('file')}><Icon name="upload" size={16} /> Upload file</button>
            <button role="tab" aria-selected={mode === 'text'} className={mode === 'text' ? 'on' : ''} onClick={() => setMode('text')}><Icon name="file" size={16} /> Paste text</button>
          </div>

          {mode === 'file' ? (
            file ? (
              <div className="file-chip"><Icon name={isImage ? 'image' : 'file'} size={22} /><span>{file.name}</span><small className="muted">{Math.max(1, Math.round(file.size / 1024))} KB</small>
                <button className="btn ghost sm" onClick={() => { setFile(null); if (input.current) input.current.value = '' }} aria-label="Remove file"><Icon name="x" size={14} /></button></div>
            ) : (
              <label className={`drop-zone ${over ? 'over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
                onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]) }}>
                <Icon name="upload" size={34} />
                <b>Drag & drop your report here</b>
                <span className="muted">or click to browse · PDF, PNG, JPG, TXT, DOCX · up to 15 MB</span>
                <input ref={input} type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.docx" onChange={(e) => pick(e.target.files[0])} />
              </label>
            )
          ) : (
            <>
              <textarea rows={9} aria-label="Report text" value={text} onChange={(e) => setText(e.target.value)} placeholder={'HbA1c: 7.4 %\nFasting Blood Glucose: 142 mg/dL'} />
              <button className="btn ghost sm" style={{ marginTop: '.5rem' }} onClick={() => setText(SAMPLE_REPORT)}>Use a sample report</button>
            </>
          )}
          {mode === 'file' && isImage && !ocr && <div className="warn">Photo reading (OCR) is not installed on this computer, so PNG/JPG files cannot be read. Use a PDF or paste the text instead.</div>}
          <Err text={error} />
          <button className="btn block" style={{ marginTop: '1rem' }} disabled={busy || !ready} onClick={analyse}>{busy ? 'Reading report…' : 'Analyse report'}</button>
          <p className="demo" style={{ marginBottom: 0 }}><Icon name="shield" size={13} /> Values are taken exactly as printed. Classification uses fixed ADA reference ranges, not the language model.</p>
        </div>

        <div className="card">
          {!res && !busy && (
            <div className="empty"><Icon name="flask" size={40} /><div><b>No report analysed yet</b></div><div>Your results will appear here, with a range bar for every value.</div></div>
          )}
          {busy && <div className="empty"><Icon name="clock" size={40} /><div>Reading your report…</div></div>}
          {res && entries.length === 0 && <div className="warn">No diabetes-related values were found in this report.{res.warning && ` ${res.warning}`}</div>}
          {res?.warning && entries.length > 0 && <div className="warn">{res.warning}</div>}
          {res && entries.length > 0 && (<>
            <div className="summary">
              <div><b>{sum.total}</b><span className="muted">values found</span></div>
              <div className="good"><b>{sum.good}</b><span className="muted">in range</span></div>
              <div className="warn-c"><b>{sum.attention}</b><span className="muted">need attention</span></div>
            </div>
            {entries.map(([k, v]) => <LabRow key={k} param={k} v={v} />)}
            <p className="muted">Extraction method: {res.method}. A single lab value is not a diagnosis.</p>
            <div className="next-box">
              <b>What would you like to do next?</b>
              <div className="row" style={{ marginTop: '.6rem' }}>
                <button className="btn ghost" onClick={() => nav('/assistant', { state: { reportText: res.text, prompt: 'Please explain my lab report results.' } })}><Icon name="chat" size={17} /> Ask AI to explain</button>
                <button className="btn amber" onClick={() => nav(`/doctors${cats[0] ? `?cat=${encodeURIComponent(cats[0])}` : ''}`)}><Icon name="steth" size={17} /> Consult a doctor</button>
              </div>
              {cats.length > 0 && <p className="muted" style={{ marginBottom: 0 }}>Suggested: {cats.map((c, i) => <span key={c}>{i > 0 && ' · '}<Link to={`/doctors?cat=${encodeURIComponent(c)}`}>{c}</Link></span>)}. This report can be shared with the doctor when you book.</p>}
            </div>
          </>)}
        </div>
      </div>
    </div>
  )
}
