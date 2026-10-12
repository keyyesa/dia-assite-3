import { useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Err, Ok, Avatar } from '../components.jsx'

export default function Profile() {
  const { user, setUser } = useAuth()
  const [name, setName] = useState(user.name)
  const [type, setType] = useState(user.diabetes_type || 'Type 2 diabetes')
  const [pw, setPw] = useState({ old_password: '', new_password: '', again: '' })
  const [msg, setMsg] = useState({ ok: '', err: '' })
  const [pmsg, setPmsg] = useState({ ok: '', err: '' })

  const saveProfile = async (e) => {
    e.preventDefault(); setMsg({ ok: '', err: '' })
    try {
      const u = await api.put('/auth/profile', { name, diabetes_type: user.role === 'patient' ? type : null })
      setUser({ ...user, ...u }); setMsg({ ok: 'Profile saved.', err: '' })
    } catch (err) { setMsg({ ok: '', err: err.message }) }
  }
  const savePassword = async (e) => {
    e.preventDefault(); setPmsg({ ok: '', err: '' })
    if (pw.new_password !== pw.again) { setPmsg({ ok: '', err: 'The new passwords do not match.' }); return }
    try {
      await api.post('/auth/password', { old_password: pw.old_password, new_password: pw.new_password })
      setPw({ old_password: '', new_password: '', again: '' }); setPmsg({ ok: 'Password changed.', err: '' })
    } catch (err) { setPmsg({ ok: '', err: err.message }) }
  }

  return (
    <div className="wrap">
      <div className="page-head row"><Avatar name={user.name} size="lg" /><div><h2 style={{ margin: 0 }}>My profile</h2><p>{user.email} · <span className="badge">{user.role}</span></p></div></div>
      <div className="grid g2" style={{ alignItems: 'start' }}>
        <form className="card" onSubmit={saveProfile}>
          <h3>Personal details</h3>
          <label style={{ marginTop: 0 }}>Full name</label><input required value={name} onChange={(e) => setName(e.target.value)} />
          <label>Email</label><input value={user.email} disabled />
          {user.role === 'patient' && (<><label>Diabetes type</label>
            <select value={type} onChange={(e) => setType(e.target.value)}><option>Type 1 diabetes</option><option>Type 2 diabetes</option><option>Gestational diabetes</option><option>Pre-diabetes</option></select></>)}
          <Err text={msg.err} /><Ok text={msg.ok} />
          <button className="btn" style={{ marginTop: '1rem' }}>Save changes</button>
        </form>
        <form className="card" onSubmit={savePassword}>
          <h3>Change password</h3>
          <label style={{ marginTop: 0 }}>Current password</label><input type="password" required autoComplete="current-password" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} />
          <label>New password (at least 6 characters)</label><input type="password" required minLength={6} autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          <label>Repeat new password</label><input type="password" required minLength={6} autoComplete="new-password" value={pw.again} onChange={(e) => setPw({ ...pw, again: e.target.value })} />
          <Err text={pmsg.err} /><Ok text={pmsg.ok} />
          <button className="btn" style={{ marginTop: '1rem' }}>Change password</button>
        </form>
      </div>
    </div>
  )
}
