import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Err, Ok, Modal } from '../components.jsx'

export default function Admin() {
  const [ov, setOv] = useState(null)
  const [users, setUsers] = useState([])
  const [kb, setKb] = useState(null)
  const [fb, setFb] = useState(null)
  const [contact, setContact] = useState([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState('')
  const [blogs, setBlogs] = useState([])
  const [blog, setBlog] = useState(null)   // blog being created / edited

  const load = () => {
    api.get('/admin/overview').then(setOv).catch((e) => setError(e.message))
    api.get('/admin/users').then(setUsers).catch(() => {})
    api.get('/kb/status').then(setKb).catch(() => {})
    api.get('/admin/feedback').then(setFb).catch(() => {})
    api.get('/admin/contact').then(setContact).catch(() => {})
    api.get('/blogs').then(setBlogs).catch(() => {})
  }
  useEffect(() => { load() }, [])
  const run = async (fn, msg, key = '') => {
    setError(''); setOk(''); setBusy(key)
    try { const r = await fn(); setOk(typeof msg === 'function' ? msg(r) : msg); load() } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const pending = users.filter((u) => u.role === 'doctor' && !u.approved)
  const Stat = ({ n, l }) => <div className="card stat"><b>{n}</b><span className="muted">{l}</span></div>

  return (
    <div className="wrap">
      <h2>Administration</h2>
      <Err text={error} /><Ok text={ok} />
      {ov && <div className="grid g4"><Stat n={ov.patients} l="Patients" /><Stat n={ov.doctors} l="Approved doctors" /><Stat n={ov.pending_doctors} l="Doctors awaiting approval" /><Stat n={ov.appointments} l="Appointments" /><Stat n={ov.upcoming} l="Upcoming" /><Stat n={ov.chat_messages} l="AI chat messages" /></div>}

      <div className="card" style={{ marginTop: '1rem' }}><h3>Doctor approvals</h3>
        {pending.length === 0 && <p className="muted">No doctors waiting.</p>}
        {pending.map((u) => <div key={u.id} className="row between" style={{ padding: '.4rem 0' }}><span>{u.name} · {u.email}</span>
          <button className="btn sm" onClick={() => run(() => api.post(`/admin/doctors/${u.doctor_id}/approval`, { approved: true }), `${u.name} approved.`)}>Approve</button></div>)}
      </div>

      <div className="card" style={{ marginTop: '1rem' }}><h3>Knowledge base (RAG training)</h3>
        {kb && <>
          <p className="muted">Index: {kb.index_exists ? `trained (${kb.n_chunks} chunks, ${kb.embedding_model})` : 'not trained yet'} {kb.trained_at ? `· ${kb.trained_at}` : ''}</p>
          {kb.pending && <div className="warn">{kb.n_pending} document change(s) not yet trained. Press Train.</div>}
          <table><thead><tr><th>Document</th><th>Size</th><th>Status</th><th>Chunks</th></tr></thead>
            <tbody>{kb.documents.map((d) => <tr key={d.name}><td>{d.name}</td><td>{Math.round(d.size / 1024)} KB</td><td><span className={`badge ${d.status === 'trained' ? 'green' : 'amber'}`}>{d.status}</span></td><td>{d.chunks ?? '-'}</td></tr>)}</tbody></table>
        </>}
        <div className="row" style={{ marginTop: '.8rem' }}>
          <input type="file" style={{ flex: 1 }} accept=".pdf,.txt,.md,.docx" id="kbfile" />
          <button className="btn ghost" disabled={busy === 'up'} onClick={() => { const f = document.getElementById('kbfile').files[0]; if (!f) return setError('Choose a file first.'); const fd = new FormData(); fd.append('file', f); run(() => api.form('/kb/upload', fd), (r) => `${r.name}: ${r.outcome}. ${r.note}`, 'up') }}>Upload document</button>
          <button className="btn" disabled={busy === 'train'} onClick={() => run(() => api.post('/kb/train'), (r) => `Training finished: ${r.n_docs} documents, ${r.n_chunks} chunks in ${r.seconds}s.`, 'train')}>{busy === 'train' ? 'Training…' : 'Train'}</button>
          <button className="btn ghost" disabled={busy === 'train'} onClick={() => run(() => api.post('/kb/train?full=true'), 'Full retraining finished.', 'train')}>Full retrain</button>
        </div>
      </div>

      <div className="grid g2" style={{ marginTop: '1rem' }}>
        <div className="card"><h3>Answer feedback</h3>{fb && <p>👍 {fb.helpful} · 👎 {fb.not_helpful} · {fb.answers} answers</p>}</div>
        <div className="card"><h3>Contact messages</h3>{contact.length === 0 && <p className="muted">None.</p>}
          {contact.slice(0, 8).map((m) => <div key={m.id} style={{ borderBottom: '1px solid var(--border)', padding: '.3rem 0' }}><b>{m.name}</b> ({m.email})<div className="muted">{m.message}</div></div>)}</div>
      </div>


      <div className="card" style={{ marginTop: '1rem' }}>
        <div className="row between"><h3 style={{ margin: 0 }}>Blog articles</h3><button className="btn sm" onClick={() => setBlog({ title: '', category: '', summary: '', body: '' })}>+ New article</button></div>
        <table><tbody>{blogs.map((b) => <tr key={b.id}><td>{b.title}</td><td className="muted">{b.category}</td>
          <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
            <button className="btn ghost sm" onClick={async () => setBlog(await api.get(`/blogs/${b.id}`))}>Edit</button>{' '}
            <button className="btn danger sm" onClick={() => confirm('Delete this article?') && run(() => api.del(`/admin/blogs/${b.id}`), 'Article deleted.')}>Delete</button></td></tr>)}</tbody></table>
      </div>
      {blog && (
        <Modal title={blog.id ? 'Edit article' : 'New article'} onClose={() => setBlog(null)}>
          <label style={{ marginTop: 0 }}>Title</label><input value={blog.title} onChange={(e) => setBlog({ ...blog, title: e.target.value })} />
          <label>Category</label><input value={blog.category} onChange={(e) => setBlog({ ...blog, category: e.target.value })} placeholder="e.g. Daily life" />
          <label>Short summary</label><input value={blog.summary} onChange={(e) => setBlog({ ...blog, summary: e.target.value })} />
          <label>Article text</label><textarea rows={8} value={blog.body} onChange={(e) => setBlog({ ...blog, body: e.target.value })} />
          <button className="btn" style={{ marginTop: '.8rem' }} disabled={!blog.title.trim() || !blog.body.trim()} onClick={async () => {
            const body = { title: blog.title, category: blog.category, summary: blog.summary, body: blog.body }
            await run(() => (blog.id ? api.put(`/admin/blogs/${blog.id}`, body) : api.post('/admin/blogs', body)), 'Article saved.'); setBlog(null)
          }}>Save article</button>
        </Modal>)}

      <div className="card" style={{ marginTop: '1rem' }}><h3>Users</h3>
        <table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr></thead>
          <tbody>{users.map((u) => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.active ? 'active' : 'disabled'}</td>
            <td>{u.role !== 'admin' && <button className="btn ghost sm" onClick={() => run(() => api.post(`/admin/users/${u.id}/active`, { active: !u.active }), 'Updated.')}>{u.active ? 'Disable' : 'Enable'}</button>}</td></tr>)}</tbody></table>
      </div>
    </div>
  )
}
