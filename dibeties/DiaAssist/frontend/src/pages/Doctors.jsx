import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, money } from '../api.js'
import { Err, Avatar } from '../components.jsx'
import { Icon } from '../icons.jsx'
import { loadReport } from '../lib/report.js'

export default function Doctors() {
  const [list, setList] = useState([])
  const [cats, setCats] = useState([])
  const [clinics, setClinics] = useState([])
  const [params] = useSearchParams()
  const [q, setQ] = useState(''); const [category, setCategory] = useState(params.get('cat') || ''); const [clinic, setClinic] = useState(''); const [maxFee, setMaxFee] = useState('')
  const [error, setError] = useState('')
  const hasReport = !!loadReport()

  useEffect(() => { api.get('/categories').then(setCats).catch(() => {}); api.get('/clinics').then(setClinics).catch(() => {}) }, [])
  useEffect(() => {
    const p = new URLSearchParams()
    if (q) p.set('q', q); if (category) p.set('category', category); if (clinic) p.set('clinic', clinic); if (maxFee) p.set('max_fee', maxFee)
    const t = setTimeout(() => api.get('/doctors?' + p).then((d) => { setList(d); setError('') }).catch((e) => setError(e.message)), 250)
    return () => clearTimeout(t)
  }, [q, category, clinic, maxFee])

  const catName = (c) => (typeof c === 'string' ? c : c.category || c.name)
  return (
    <div className="wrap">
      <div className="page-head"><h2>Diabetes specialists</h2><p>Choose a doctor, see free days and book in a minute. Profiles are demonstration data.</p></div>
      {hasReport && <div className="ok">Your analysed report is ready: you can attach it when you book.</div>}
      {params.get('cat') && category && <div className="warn">Showing <b>{category}</b> doctors suggested by your report. <a href="#" onClick={(e) => { e.preventDefault(); setCategory('') }}>Show all</a></div>}
      <div className="card row" style={{ marginBottom: '1rem' }}>
        <input style={{ flex: 2, minWidth: 180 }} placeholder="Search by name or qualification" aria-label="Search doctors" value={q} onChange={(e) => setQ(e.target.value)} />
        <select style={{ flex: 1 }} aria-label="Category" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">All categories</option>{cats.map((c) => <option key={catName(c)}>{catName(c)}</option>)}</select>
        <select style={{ flex: 1 }} aria-label="Location" value={clinic} onChange={(e) => setClinic(e.target.value)}><option value="">All locations</option>{clinics.map((c) => <option key={c.id} value={c.name}>{c.name}</option>)}</select>
        <input style={{ flex: 1, minWidth: 110 }} type="number" min="0" placeholder="Max fee" aria-label="Maximum fee" value={maxFee} onChange={(e) => setMaxFee(e.target.value)} />
      </div>
      <Err text={error} />
      {list.length === 0 && !error && <div className="card empty"><Icon name="steth" size={32} /><div>No doctors match these filters.</div></div>}
      <div className="grid g3">
        {list.map((d) => (
          <div key={d.id} className="card doc-card">
            <div className="row"><Avatar name={d.name} /><div style={{ flex: 1 }}><b>{d.name}</b><div className="muted">{d.qualification}</div></div></div>
            <div className="row"><span className="badge">{d.category}</span><span className="badge gray">{d.experience_years} yrs experience</span></div>
            <p className="muted" style={{ margin: '.2rem 0' }}>{d.bio}</p>
            <div className="muted"><Icon name="pin" size={15} /> {[...new Set(d.clinics.map((c) => c.name))].join(', ') || 'No clinic set'}</div>
            <div className="row between" style={{ marginTop: 'auto', paddingTop: '.4rem' }}>
              <div><b>{money(d.fee)}</b><div className="muted"><Icon name="clock" size={14} /> {d.next_free ? `Next free: ${d.next_free}` : 'No free slots soon'}</div></div>
              <Link className="btn" to={`/doctors/${d.id}`}>View & book</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
