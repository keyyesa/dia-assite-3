import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, isoDate } from '../api.js'
import { Err, Ok, Modal, ReportSummary, Avatar } from '../components.jsx'
import { Icon } from '../icons.jsx'

const todayIso = () => isoDate(new Date())

export default function DoctorDashboard() {
  const [start, setStart] = useState(todayIso())
  const [week, setWeek] = useState(null)
  const [clinics, setClinics] = useState([])
  const [appts, setAppts] = useState([])
  const [tab, setTab] = useState('upcoming')
  const [sel, setSel] = useState(null)
  const [modal, setModal] = useState(null)   // {kind:'report'|'notes', a}
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [reason, setReason] = useState('Emergency')
  const [clinicId, setClinicId] = useState('')
  const [profile, setProfile] = useState({ qualification: '', fee: '', bio: '', experience_years: '' })

  const load = () => {
    api.get(`/doctor/week?start=${start}`).then(setWeek).catch((e) => setError(e.message))
    api.get('/appointments').then(setAppts).catch(() => {})
  }
  useEffect(() => { load() }, [start])
  useEffect(() => { api.get('/clinics').then((c) => { setClinics(c); if (c[0]) setClinicId(c[0].id) }).catch(() => {}) }, [])

  const run = async (fn, msg) => {
    setError(''); setOk('')
    try { await fn(); setOk(msg); load(); return true } catch (e) { setError(e.message); return false }
  }
  const shift = (n) => { const d = new Date(start + 'T00:00:00'); d.setDate(d.getDate() + n); setStart(isoDate(d)) }
  const day = week?.days.find((d) => d.date === sel)
  const choose = (d) => { setSel(d.date); if (d.clinic?.id) setClinicId(d.clinic.id) }
  const list = appts.filter((a) => a.state === tab).sort((a, b) => (tab === 'upcoming' ? 1 : -1) * (a.date + a.time).localeCompare(b.date + b.time))
  const canNote = (a) => a.state === 'completed' || a.date <= todayIso()

  return (
    <div className="wrap">
      <div className="page-head"><h2>My clinic</h2><p>Your calendar, patients, shared reports and visit notes.</p></div>
      <Err text={error} /><Ok text={ok} />
      <div className="card">
        <div className="row between"><h3 style={{ margin: 0 }}>Weekly calendar</h3>
          <div className="row"><button className="btn ghost sm" onClick={() => shift(-7)}>← Previous</button><button className="btn ghost sm" onClick={() => setStart(todayIso())}>Today</button><button className="btn ghost sm" onClick={() => shift(7)}>Next →</button></div></div>
        <p className="muted"><span className="chip free" style={{ display: 'inline' }}>free</span> <span className="chip busy" style={{ display: 'inline' }}>booked</span> — click a day for details and actions.</p>
        <div className="cal">
          {week?.days.map((d) => {
            const busy = d.slots.filter((s) => s.booked).length
            return (
              <div key={d.date} className={`day ${!d.working ? 'off' : ''} ${d.cancelled ? 'cx' : ''}`} style={{ outline: sel === d.date ? '2px solid var(--teal)' : 'none' }} onClick={() => choose(d)}>
                <b>{d.weekday} {d.date.slice(5)}</b>
                {!d.working && <div>Off</div>}
                {d.cancelled && <div className="badge red">Cancelled</div>}
                {d.working && !d.cancelled && <><div className="muted"><Icon name="pin" size={13} /> {d.clinic?.name}</div><div>{busy} booked / {d.slots.length - busy} free</div></>}
              </div>
            )
          })}
        </div>
      </div>

      {day && (
        <div className="card" style={{ marginTop: '1rem' }}>
          <h3>{day.date} ({day.weekday})</h3>
          {!day.working && <p className="muted">Not a working day. You can still set a clinic location for an extra day below.</p>}
          {day.cancelled && <div className="warn">Day cancelled: {day.reason} <button className="btn sm" style={{ marginLeft: 8 }} onClick={() => run(() => api.post('/doctor/reopen-day', { date: day.date }), 'Day reopened.')}>Reopen day</button></div>}
          {day.working && <div>{day.slots.map((s) => <span key={s.time} className={`chip ${s.booked ? 'busy' : 'free'}`}>{s.time} — {s.booked ? `Token #${s.token} · ${s.patient}` : 'free'}</span>)}</div>}
          <div className="grid g2" style={{ marginTop: '1rem' }}>
            <div><label style={{ marginTop: 0 }}>Emergency: cancel all appointments this day</label>
              <input value={reason} onChange={(e) => setReason(e.target.value)} />
              <button className="btn danger" style={{ marginTop: '.5rem' }} disabled={day.cancelled} onClick={() => confirm(`Cancel ALL appointments on ${day.date}? Every patient will be notified.`) && run(() => api.post('/doctor/cancel-day', { date: day.date, reason }), 'Day cancelled and patients notified.')}>Cancel whole day</button></div>
            <div><label style={{ marginTop: 0 }}>Clinic location for this day</label>
              <select value={clinicId} onChange={(e) => setClinicId(e.target.value)}>{clinics.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
              <button className="btn" style={{ marginTop: '.5rem' }} onClick={() => run(() => api.post('/doctor/location', { date: day.date, clinic_id: Number(clinicId) }), 'Location updated; affected patients were notified.')}>Change location</button></div>
          </div>
        </div>
      )}

      <div className="grid g2" style={{ marginTop: '1rem', alignItems: 'start' }}>
        <div className="card"><h3>Patients</h3>
          <div className="tabs"><button className={tab === 'upcoming' ? 'on' : ''} onClick={() => setTab('upcoming')}>Upcoming</button><button className={tab === 'completed' ? 'on' : ''} onClick={() => setTab('completed')}>Completed</button></div>
          {list.length === 0 && <p className="muted">No {tab} appointments.</p>}
          {list.slice(0, 20).map((a) => (
            <div key={a.id} style={{ padding: '.6rem 0', borderBottom: '1px solid var(--border)' }}>
              <div className="row between">
                <div className="row"><Avatar name={a.patient_name} size="sm" /><div><b>{a.patient_name}</b><div className="muted">{a.date} {a.time} · token #{a.token} · {a.payment_method === 'online' ? 'paid online' : 'cash'}</div></div></div>
              </div>
              <div className="row" style={{ marginTop: '.4rem' }}>
                {a.report && <button className="btn ghost sm" onClick={() => setModal({ kind: 'report', a })}><Icon name="flask" size={14} /> View report</button>}
                {canNote(a) && <button className="btn ghost sm" onClick={() => { setNotes(a.doctor_notes || ''); setModal({ kind: 'notes', a }) }}><Icon name="file" size={14} /> {a.doctor_notes ? 'Edit notes' : 'Visit notes'}</button>}
                <Link className="btn ghost sm" to={`/messages?with=${a.patient_id}`}><Icon name="msg" size={14} /> Message</Link>
                {a.state === 'upcoming' && <button className="btn danger sm" onClick={() => { const r = prompt('Reason for cancelling:', ''); if (r !== null) run(() => api.post(`/appointments/${a.id}/cancel`, { reason: r }), 'Appointment cancelled; patient notified.') }}>Cancel</button>}
              </div>
            </div>
          ))}
        </div>
        <div className="card"><h3>Edit my profile</h3>
          <label style={{ marginTop: 0 }}>Qualification</label><input value={profile.qualification} onChange={(e) => setProfile({ ...profile, qualification: e.target.value })} />
          <div className="row"><div style={{ flex: 1 }}><label>Fee (Rs)</label><input type="number" value={profile.fee} onChange={(e) => setProfile({ ...profile, fee: e.target.value })} /></div>
            <div style={{ flex: 1 }}><label>Experience (yrs)</label><input type="number" value={profile.experience_years} onChange={(e) => setProfile({ ...profile, experience_years: e.target.value })} /></div></div>
          <label>Bio</label><textarea rows={3} value={profile.bio} onChange={(e) => setProfile({ ...profile, bio: e.target.value })} />
          <p className="muted">Leave a field empty to keep it unchanged.</p>
          <button className="btn" onClick={() => { const b = {}; if (profile.qualification) b.qualification = profile.qualification; if (profile.fee !== '') b.fee = Number(profile.fee); if (profile.bio) b.bio = profile.bio; if (profile.experience_years !== '') b.experience_years = Number(profile.experience_years); run(() => api.put('/doctor/profile', b), 'Profile saved.') }}>Save profile</button></div>
      </div>

      {modal?.kind === 'report' && <Modal title={`${modal.a.patient_name}: shared report`} onClose={() => setModal(null)}><ReportSummary report={modal.a.report} /></Modal>}
      {modal?.kind === 'notes' && (
        <Modal title={`Visit notes: ${modal.a.patient_name}`} onClose={() => setModal(null)}>
          <textarea rows={6} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Findings, advice, medicines, next visit…" />
          <p className="muted">The patient can read these notes in their appointment history.</p>
          <button className="btn" disabled={!notes.trim()} onClick={async () => { if (await run(() => api.post(`/appointments/${modal.a.id}/notes`, { notes }), 'Notes saved; patient notified.')) setModal(null) }}>Save notes</button>
        </Modal>)}
    </div>
  )
}
