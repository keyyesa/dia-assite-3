import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, money, nextDays, isoDate, dayLabel } from '../api.js'
import { Err, Ok, Modal, stateBadge } from '../components.jsx'

function Resched({ a, onClose, onDone }) {
  const [date, setDate] = useState(a.date)
  const [day, setDay] = useState(null)
  const [time, setTime] = useState('')
  const [emergency, setEmergency] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.get(`/doctors/${a.doctor_id}/slots?date=${date}`).then((d) => { setDay(d); setTime('') }).catch((e) => setError(e.message)) }, [date])
  const go = async () => {
    try { await api.post(`/appointments/${a.id}/reschedule`, { date, time, emergency }); onDone('Appointment moved. A new token number was issued.') }
    catch (e) { setError(e.message) }
  }
  return (
    <Modal title="Reschedule / postpone" onClose={onClose}>
      <p className="muted">{a.doctor_name} · currently {a.date} {a.time} · {a.clinic_name}</p>
      <div className="dates">{nextDays(21).map((d) => <button key={isoDate(d)} className={date === isoDate(d) ? 'on' : ''} onClick={() => setDate(isoDate(d))}>{dayLabel(d)}</button>)}</div>
      {day && (day.working && !day.cancelled
        ? <><p className="muted">📍 {day.clinic?.name} on this day</p><div className="slots">{day.slots.map((s) => <button key={s.time} disabled={!s.free} className={`slot ${time === s.time ? 'on' : ''}`} onClick={() => setTime(s.time)}>{s.time}</button>)}</div></>
        : <p className="muted">No clinic on this day{day.cancelled ? ' (cancelled by doctor)' : ''}.</p>)}
      <label><input type="checkbox" style={{ width: 'auto' }} checked={emergency} onChange={(e) => setEmergency(e.target.checked)} /> This is an emergency postponement</label>
      <Err text={error} />
      <button className="btn" style={{ marginTop: '.8rem' }} disabled={!time} onClick={go}>Confirm new time</button>
    </Modal>
  )
}

export default function Appointments() {
  const [list, setList] = useState([])
  const [tab, setTab] = useState('upcoming')
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const load = () => api.get('/appointments').then(setList).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const cancel = async (a) => {
    const reason = prompt('Reason for cancelling (optional):', '')
    if (reason === null) return
    try { await api.post(`/appointments/${a.id}/cancel`, { reason }); setOk(a.payment_status === 'paid' ? 'Cancelled. Your demo payment is marked as refunded.' : 'Appointment cancelled.'); setError(''); load() }
    catch (e) { setError(e.message) }
  }
  const remove = async (a) => {
    if (!confirm('Remove this record from your history?')) return
    try { await api.del(`/appointments/${a.id}`); load() } catch (e) { setError(e.message) }
  }
  const shown = list.filter((a) => (tab === 'all' ? true : a.state === tab))

  return (
    <div className="wrap">
      <div className="row between"><h2>My appointments</h2><Link className="btn" to="/doctors">Book new</Link></div>
      <div className="tabs" style={{ maxWidth: 480 }}>
        {['upcoming', 'completed', 'cancelled', 'all'].map((t) => <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t[0].toUpperCase() + t.slice(1)}</button>)}
      </div>
      <Err text={error} /><Ok text={ok} />
      {shown.length === 0 && <p className="muted">Nothing here yet.</p>}
      <div className="grid g2">
        {shown.map((a) => (
          <div className="card" key={a.id}>
            <div className="row between"><h3>{a.doctor_name}</h3>{stateBadge(a)}</div>
            <div className="muted">{a.category}</div>
            <p style={{ margin: '.5rem 0' }}>📅 {a.date} at {a.time} · 📍 {a.clinic_name}</p>
            <div className="row">
              <span className="badge">Token #{a.token}</span>
              <span className="badge gray">{money(a.fee)} · {a.payment_method === 'online' ? `online (${a.payment_status})` : 'cash at clinic'}</span>
            </div>
            {a.cancel_reason && <p className="muted">Reason: {a.cancel_reason}</p>}
            {a.report && <p className="muted" style={{ margin: '.4rem 0 0' }}>Report shared with the doctor ({Object.keys(a.report).length} values).</p>}
            {a.doctor_notes && <div className="ok" style={{ marginBottom: 0 }}><b>Doctor's notes:</b> {a.doctor_notes}</div>}
            <div className="row" style={{ marginTop: '.7rem' }}>
              {a.state === 'upcoming' && <>
                <button className="btn sm" onClick={() => setRes(a)}>Reschedule</button>
                <button className="btn danger sm" onClick={() => cancel(a)}>Cancel</button></>}
              {a.state === 'cancelled' && <button className="btn sm" onClick={() => setRes(a)}>Book again</button>}
              {a.state !== 'upcoming' && <button className="btn danger sm" onClick={() => remove(a)}>Delete record</button>}
              <Link className="btn ghost sm" to={`/messages?with=${a.doctor_user_id}`}>Message doctor</Link>
            </div>
          </div>
        ))}
      </div>
      {res && res.state === 'upcoming' && <Resched a={res} onClose={() => setRes(null)} onDone={(m) => { setRes(null); setOk(m); load() }} />}
      {res && res.state === 'cancelled' && <Modal title="Book again" onClose={() => setRes(null)}><p>Open the doctor profile to choose a new slot.</p><Link className="btn" to={`/doctors/${res.doctor_id}`}>Go to {res.doctor_name}</Link></Modal>}
    </div>
  )
}
