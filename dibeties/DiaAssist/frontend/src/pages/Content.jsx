import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { Err, Ok } from '../components.jsx'

export function Blogs() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  useEffect(() => { api.get('/blogs').then(setList).catch((e) => setError(e.message)) }, [])
  return (
    <div className="wrap"><h2>Health blog</h2><Err text={error} />
      <div className="grid g2">{list.map((b) => (
        <Link key={b.id} to={`/blogs/${b.id}`} className="card" style={{ color: 'inherit' }}>
          <span className="badge">{b.category}</span><h3 style={{ marginTop: '.5rem' }}>{b.title}</h3><p className="muted">{b.summary}</p><span className="demo">{b.created_at?.slice(0, 10)}</span>
        </Link>))}</div>
    </div>
  )
}

export function BlogPost() {
  const { id } = useParams()
  const [b, setB] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.get(`/blogs/${id}`).then(setB).catch((e) => setError(e.message)) }, [id])
  return (
    <div className="wrap" style={{ maxWidth: 760 }}><Link to="/blogs">← All articles</Link><Err text={error} />
      {b && <div className="card" style={{ marginTop: '.8rem' }}><span className="badge">{b.category}</span><h2>{b.title}</h2><p className="muted">{b.created_at?.slice(0, 10)}</p>
        <div style={{ whiteSpace: 'pre-wrap' }}>{b.body}</div><p className="demo">General education only; not medical advice.</p></div>}
    </div>
  )
}

export function Contact() {
  const [f, setF] = useState({ name: '', email: '', message: '' })
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const submit = async (e) => {
    e.preventDefault(); setError(''); setOk('')
    try { await api.post('/contact', f); setOk('Thank you — your message has been received.'); setF({ name: '', email: '', message: '' }) } catch (err) { setError(err.message) }
  }
  return (
    <div className="wrap" style={{ maxWidth: 560 }}><div className="card"><h2>Contact us</h2>
      <p className="muted">Questions, feedback or problems? Send us a message.</p>
      <form onSubmit={submit}>
        <label>Name</label><input required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <label>Email</label><input required type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <label>Message</label><textarea required rows={5} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} />
        <Err text={error} /><Ok text={ok} />
        <button className="btn" style={{ marginTop: '.8rem' }}>Send</button>
      </form></div></div>
  )
}
