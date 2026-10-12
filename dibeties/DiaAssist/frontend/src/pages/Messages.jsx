import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Err } from '../components.jsx'

export default function Messages() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const [people, setPeople] = useState([])
  const [other, setOther] = useState(null)
  const [thread, setThread] = useState([])
  const [body, setBody] = useState('')
  const [error, setError] = useState('')
  const end = useRef(null)

  useEffect(() => { api.get('/messages/conversations').then((p) => { setPeople(p); const want = Number(params.get('with')); setOther(p.some((x) => x.user_id === want) ? want : p[0]?.user_id ?? null) }).catch((e) => setError(e.message)) }, [])
  useEffect(() => {
    if (!other) return
    let stop = false
    const pull = () => api.get(`/messages/${other}`).then((t) => { if (!stop) setThread(t) }).catch((e) => setError(e.message))
    pull(); const t = setInterval(pull, 4000)
    return () => { stop = true; clearInterval(t) }
  }, [other])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [thread])

  const send = async () => {
    if (!body.trim()) return
    try { await api.post(`/messages/${other}`, { body }); setBody(''); setThread(await api.get(`/messages/${other}`)) } catch (e) { setError(e.message) }
  }
  return (
    <div className="wrap">
      <h2>Messages</h2>
      <p className="muted">You can message a {user.role === 'patient' ? 'doctor' : 'patient'} once you share an appointment.</p>
      {people.length === 0 && <div className="card">No conversations yet. {user.role === 'patient' ? 'Book an appointment to start chatting with a doctor.' : 'Patients appear here once they book with you.'}</div>}
      {people.length > 0 && <div className="chat">
        <div className="card chat-side">{people.map((p) => <div key={p.user_id} className={`conv ${other === p.user_id ? 'on' : ''}`} onClick={() => setOther(p.user_id)}><span>{p.name}</span>{p.unread > 0 && <span className="badge red">{p.unread}</span>}</div>)}</div>
        <div className="card chat-main">
          <div className="msgs">{thread.length === 0 && <p className="muted">No messages yet. Say hello.</p>}
            {thread.map((m) => <div key={m.id} className={`m ${m.sender_id === user.id ? 'user' : 'bot'}`}>{m.body}<div style={{ fontSize: '.7rem', opacity: .7 }}>{m.created_at?.replace('T', ' ').slice(0, 16)}</div></div>)}<div ref={end} /></div>
          <div style={{ padding: '.8rem', borderTop: '1px solid var(--border)' }}><Err text={error} />
            <div className="row"><input style={{ flex: 1 }} value={body} onChange={(e) => setBody(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()} placeholder="Write a message…" /><button className="btn" onClick={send}>Send</button></div></div>
        </div>
      </div>}
    </div>
  )
}
