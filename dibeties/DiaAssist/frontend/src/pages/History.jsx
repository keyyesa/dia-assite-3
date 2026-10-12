import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, money } from '../api.js'
import { useAuth } from '../auth.jsx'
import { stateBadge } from '../components.jsx'

export default function History() {
  const { user } = useAuth()
  const [appts, setAppts] = useState([])
  const [convs, setConvs] = useState([])
  useEffect(() => { api.get('/appointments').then(setAppts).catch(() => {}); api.get('/chat/conversations').then(setConvs).catch(() => {}) }, [])
  const upcoming = appts.filter((a) => a.state === 'upcoming')
  const spent = appts.filter((a) => a.payment_status === 'paid').reduce((s, a) => s + a.fee, 0)
  const Stat = ({ n, l }) => <div className="card stat"><b>{n}</b><span className="muted">{l}</span></div>
  return (
    <div className="wrap">
      <h2>My dashboard & history</h2>
      <p className="muted">{user.name} · {user.diabetes_type || 'Diabetes type not set'}</p>
      <div className="grid g4">
        <Stat n={upcoming.length} l="Upcoming appointments" /><Stat n={appts.length} l="Total appointments" /><Stat n={convs.length} l="AI conversations" /><Stat n={money(spent)} l="Paid online (demo)" />
      </div>
      <div className="grid g2" style={{ marginTop: '1rem' }}>
        <div className="card"><h3>Appointment history</h3>
          {appts.length === 0 && <p className="muted">No appointments yet.</p>}
          <table><tbody>{appts.slice(0, 10).map((a) => <tr key={a.id}><td>{a.date} {a.time}</td><td>{a.doctor_name}</td><td>#{a.token}</td><td>{stateBadge(a)}</td></tr>)}</tbody></table>
          <Link to="/appointments">Manage appointments →</Link></div>
        <div className="card"><h3>Recent AI conversations</h3>
          {convs.length === 0 && <p className="muted">No conversations yet.</p>}
          <table><tbody>{convs.slice(0, 10).map((c) => <tr key={c.id}><td>{c.title}</td><td className="muted">{c.updated_at?.slice(0, 10)}</td></tr>)}</tbody></table>
          <Link to="/assistant">Open assistant →</Link></div>
      </div>
    </div>
  )
}
