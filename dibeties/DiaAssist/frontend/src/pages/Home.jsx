import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { api, money } from '../api.js'
import { Avatar } from '../components.jsx'
import { Icon } from '../icons.jsx'

const FEATURES = [
  ['flask', 'Report analysis', 'Upload a lab report (PDF or photo). Values are read exactly as printed and compared with ADA ranges.', '/report'],
  ['chat', 'AI assistant', 'Ask diabetes questions. Answers come from trusted guidelines, with the sources shown.', '/assistant'],
  ['steth', 'Book a specialist', 'Pick a specialist, see free days on a calendar and get a token number instantly.', '/doctors'],
  ['calendar', 'Manage visits', 'Cancel, reschedule or review your full appointment history.', '/appointments'],
]

export default function Home() {
  const { user } = useAuth()
  const [doctors, setDoctors] = useState([])
  const [blogs, setBlogs] = useState([])
  const [clinics, setClinics] = useState([])
  useEffect(() => {
    api.get('/doctors').then(setDoctors).catch(() => {})
    api.get('/blogs').then(setBlogs).catch(() => {})
    api.get('/clinics').then(setClinics).catch(() => {})
  }, [])
  const specialities = new Set(doctors.map((d) => d.category)).size
  const cta = !user
    ? [['/login', 'Log in to start', 'amber'], ['/doctors', 'Find a doctor', 'ghost']]
    : user.role === 'doctor' ? [['/doctor', 'Open my clinic', 'amber'], ['/messages', 'Messages', 'ghost']]
      : user.role === 'admin' ? [['/admin', 'Open admin panel', 'amber'], ['/doctors', 'View doctors', 'ghost']]
        : [['/report', 'Analyse my report', 'amber'], ['/doctors', 'Find a doctor', 'ghost']]

  return (
    <div className="wrap">
      <div className="hero">
        <div>
          <h1>{user ? `Hello, ${user.name.split(' ')[0]}.` : 'Welcome.'} Understand your diabetes reports. Talk to the right doctor.</h1>
          <p>DiaAssist AI explains your lab results with guideline-backed answers, then helps you book a specialist in a few clicks.</p>
          <div className="row" style={{ marginTop: '1.1rem' }}>
            {cta.map(([to, label, kind]) => <Link key={to} className={`btn ${kind}`} to={to}>{label}<Icon name="arrow" size={16} /></Link>)}
          </div>
        </div>
        <div className="hero-card">
          <div className="muted" style={{ color: '#ffffffc0' }}>Platform at a glance</div>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', marginTop: '.6rem' }}>
            <div className="stat"><b style={{ color: '#fff' }}>{doctors.length}</b><span>Doctors</span></div>
            <div className="stat"><b style={{ color: '#fff' }}>{specialities}</b><span>Specialities</span></div>
            <div className="stat"><b style={{ color: '#fff' }}>{clinics.length}</b><span>Locations</span></div>
          </div>
        </div>
      </div>

      <div className="grid g4">
        {FEATURES.map(([icon, t, d, to]) => (
          <Link key={t} to={user ? to : '/login'} className="card feature">
            <span className="ico"><Icon name={icon} size={22} /></span><h3>{t}</h3><span className="muted">{d}</span>
          </Link>
        ))}
      </div>

      {doctors.length > 0 && (<>
        <div className="row between" style={{ margin: '2rem 0 .8rem' }}><h2 style={{ margin: 0 }}>Featured specialists</h2><Link to="/doctors">See all doctors →</Link></div>
        <div className="grid g3">
          {doctors.slice(0, 3).map((d) => (
            <Link key={d.id} to={`/doctors/${d.id}`} className="card doc-card" style={{ color: 'inherit' }}>
              <div className="row"><Avatar name={d.name} /><div><b>{d.name}</b><div className="muted">{d.category}</div></div></div>
              <div className="muted">{d.qualification}</div>
              <div className="row between"><b>{money(d.fee)}</b><span className="muted">{d.next_free ? `Next: ${d.next_free}` : 'No free slots soon'}</span></div>
            </Link>
          ))}
        </div>
        <p className="demo">Doctor profiles are demonstration data.</p>
      </>)}

      {blogs.length > 0 && (<>
        <div className="row between" style={{ margin: '2rem 0 .8rem' }}><h2 style={{ margin: 0 }}>From the health blog</h2><Link to="/blogs">All articles →</Link></div>
        <div className="grid g3">
          {blogs.slice(0, 3).map((b) => (
            <Link key={b.id} to={`/blogs/${b.id}`} className="card" style={{ color: 'inherit' }}>
              <span className="badge">{b.category}</span><h3 style={{ marginTop: '.5rem' }}>{b.title}</h3><p className="muted" style={{ margin: 0 }}>{b.summary}</p>
            </Link>
          ))}
        </div>
      </>)}

      <p className="demo" style={{ marginTop: '2rem' }}>DiaAssist AI is decision support only and does not replace a qualified healthcare professional.</p>
    </div>
  )
}
