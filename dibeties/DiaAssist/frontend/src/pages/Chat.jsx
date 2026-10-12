import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Err } from '../components.jsx'
import { Icon } from '../icons.jsx'

export default function Chat() {
  const loc = useLocation()
  const navigate = useNavigate()
  const [convs, setConvs] = useState([])
  const [search, setSearch] = useState('')
  const [cid, setCid] = useState(null)
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState(loc.state?.prompt || '')
  const [reportText, setReportText] = useState(loc.state?.reportText || '')
  const [mode, setMode] = useState('fast')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const end = useRef(null)

  const loadConvs = (q = search) => api.get(`/chat/conversations?q=${encodeURIComponent(q)}`).then(setConvs).catch(() => {})
  useEffect(() => { const t = setTimeout(() => loadConvs(search), 250); return () => clearTimeout(t) }, [search])
  // the prefilled prompt/report came through router state: clear it so a page refresh cannot resend it
  useEffect(() => { if (loc.state) navigate(loc.pathname, { replace: true, state: null }) }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const open = async (id) => {
    setError(''); setCid(id); setReportText('')
    try {
      const m = await api.get(`/chat/conversations/${id}`)
      setMsgs(m.map((x) => ({ ...x, sources: x.sources ? String(x.sources).split('; ') : [], feedback: x.feedback || null })))
    } catch (e) { setError(e.message) }
  }
  const fresh = () => { setCid(null); setMsgs([]); setError(''); setReportText('') }

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    setError(''); setInput(''); setBusy(true)
    setMsgs((m) => [...m, { role: 'user', content: text }])
    try {
      const r = await api.post('/chat', { message: text, conversation_id: cid, mode, report_text: reportText || null })
      setCid(r.conversation_id)
      setMsgs((m) => [...m, { role: 'assistant', id: r.message_id, content: r.response, sources: r.sources, verified: r.verified, issues: r.issues, seconds: r.seconds, mode: r.mode, noInfo: r.no_information }])
      loadConvs('')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const vote = async (m, value) => {
    const v = m.feedback === value ? null : value
    await api.post(`/chat/messages/${m.id}/feedback`, { value: v }).catch(() => {})
    setMsgs((all) => all.map((x) => (x === m ? { ...x, feedback: v } : x)))
  }
  const del = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this conversation?')) return
    await api.del(`/chat/conversations/${id}`).catch(() => {})
    if (cid === id) fresh()
    loadConvs()
  }

  return (
    <div className="wrap">
      <div className="chat">
        <div className="card chat-side">
          <button className="btn" style={{ width: '100%' }} onClick={fresh}>+ New chat</button>
          <input style={{ margin: '.6rem 0' }} placeholder="Search history" value={search} onChange={(e) => setSearch(e.target.value)} />
          {convs.length === 0 && <p className="muted">No conversations.</p>}
          {convs.map((c) => (
            <div key={c.id} className={`conv ${cid === c.id ? 'on' : ''}`} onClick={() => open(c.id)}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title}</span>
              <button onClick={(e) => del(c.id, e)} title="Delete conversation" aria-label="Delete conversation"><Icon name="trash" size={16} /></button>
            </div>
          ))}
        </div>
        <div className="card chat-main">
          <div className="msgs">
            {msgs.length === 0 && <div className="muted">Ask about diabetes — for example “What is the HbA1c target for adults?”. Answers are based only on the trained guideline documents.</div>}
            {reportText && <div className="warn">Your analysed report is attached to the next question.</div>}
            {msgs.map((m, i) => (
              <div key={i} className={`m ${m.role === 'user' ? 'user' : 'bot'}`}>
                {m.content}
                {m.role === 'assistant' && (<>
                  <div className="row" style={{ marginTop: '.5rem' }}>
                    {m.verified === true || m.verified === 1 ? <span className="badge green"><Icon name="check" size={13} /> Verified against sources</span>
                      : m.verified === false || m.verified === 0 ? <span className="badge amber">Not fully verified</span>
                        : m.noInfo ? null : <span className="badge gray">Fast mode: not checked</span>}
                    {m.seconds ? <span className="muted">{m.seconds}s · {m.mode}</span> : null}
                    {m.id && <><button className="btn ghost sm" style={m.feedback === 1 ? { background: '#E4F1F0' } : {}} onClick={() => vote(m, 1)}>👍</button><button className="btn ghost sm" style={m.feedback === -1 ? { background: '#fdeaea' } : {}} onClick={() => vote(m, -1)}>👎</button></>}
                  </div>
                  {m.issues?.length > 0 && <div className="muted">Checker notes: {m.issues.join('; ')}</div>}
                  {m.sources?.length > 0 && <details><summary className="muted">Sources ({m.sources.length})</summary>
                    {m.sources.map((s, j) => <div className="src" key={j}><b>{typeof s === 'string' ? s : s.source}</b>{s.content && <div className="muted">{s.content}…</div>}</div>)}</details>}
                </>)}
              </div>
            ))}
            {busy && <div className="m bot muted">Thinking… (the first answer can take up to a minute on a laptop)</div>}
            <div ref={end} />
          </div>
          <div style={{ padding: '.8rem', borderTop: '1px solid var(--border)' }}>
            <Err text={error} />
            <div className="row">
              <select style={{ width: 130 }} value={mode} onChange={(e) => setMode(e.target.value)}><option value="fast">Fast</option><option value="full">Full (checked)</option></select>
              <textarea rows={1} style={{ flex: 1, minWidth: 200, resize: 'none' }} value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type your question…"
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
              <button className="btn" disabled={busy || !input.trim()} onClick={send}>Send<Icon name="arrow" size={16} /></button>
            </div>
            <p className="demo">Decision support only — not a replacement for a qualified healthcare professional.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

