import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api, money } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Err, Avatar } from '../components.jsx'
import { Icon } from '../icons.jsx'
import { loadReport, reportForBooking, clearReport } from '../lib/report.js'
import { summarize } from '../lib/ranges.js'

const WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function Calendar({ days, value, onPick }) {
  if (!days.length) return <p className="muted">Loading calendar…</p>
  const lead = (new Date(days[0].date + 'T00:00:00').getDay() + 6) % 7  // Monday first
  const label = (d) => (d.status === 'free' ? `${d.free} free` : d.status === 'full' ? 'Full' : d.status === 'cancelled' ? 'Cancelled' : 'Off')
  return (
    <>
      <div className="mcal" role="group" aria-label="Doctor availability">
        {DOW.map((d) => <div key={d} className="dow">{d}</div>)}
        {Array.from({ length: lead }, (_, i) => <span key={`b${i}`} className="blank" />)}
        {days.map((d) => (
          <button key={d.date} type="button" className={`${d.status} ${value === d.date ? 'sel' : ''}`} disabled={d.status !== 'free'} onClick={() => onPick(d.date)}
            title={d.clinic ? `${d.clinic}` : ''} aria-label={`${d.date}: ${label(d)}`}>
            <b>{Number(d.date.slice(8))}</b><small>{label(d)}</small>
          </button>
        ))}
      </div>
      <div className="legend">
        <span><i style={{ background: '#eaf7f1' }} />Free slots</span><span><i style={{ background: '#fff3dd' }} />Fully booked</span>
        <span><i style={{ background: '#f1f3f3' }} />Doctor not working</span><span><i style={{ background: '#fdeaea' }} />Cancelled by doctor</span>
      </div>
    </>
  )
}

export default function DoctorProfile() {
  const { id } = useParams()
  const { user } = useAuth()
  const nav = useNavigate()
  const [doc, setDoc] = useState(null)
  const [days, setDays] = useState([])
  const [date, setDate] = useState('')
  const [day, setDay] = useState(null)
  const [time, setTime] = useState('')
  const [reason, setReason] = useState('')
  const [pay, setPay] = useState('cash')
  const [card, setCard] = useState({ number: '4242 4242 4242 4242', name: '' })
  const [saved] = useState(loadReport)
  const [attach, setAttach] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)

  const loadDays = () => api.get(`/doctors/${id}/availability?days=42`).then((d) => {
    setDays(d); setDate((cur) => cur || d.find((x) => x.status === 'free')?.date || '')
  }).catch((e) => setError(e.message))
  useEffect(() => { api.get(`/doctors/${id}`).then(setDoc).catch((e) => setError(e.message)); loadDays() }, [id])
  const loadSlots = () => date && api.get(`/doctors/${id}/slots?date=${date}`).then((d) => { setDay(d); setTime('') }).catch((e) => setError(e.message))
  useEffect(() => { loadSlots() }, [id, date])

  const book = async () => {
    setError(''); setBusy(true)
    try {
      const a = await api.post('/appointments', { doctor_id: Number(id), date, time, reason, payment_method: pay, report: saved && attach ? reportForBooking(saved.values) : null })
      if (saved && attach) clearReport()
      setDone(a)
    } catch (e) { setError(e.message); loadSlots(); loadDays() } finally { setBusy(false) }
  }

  if (!doc) return <div className="wrap"><Err text={error} />{!error && 'Loading…'}</div>

  if (done) return (
    <div className="wrap narrow"><div className="card" style={{ textAlign: 'center' }}>
      <span className="badge green"><Icon name="check" size={14} /> Appointment confirmed</span>
      <p className="muted" style={{ marginTop: '1rem' }}>Your token number</p>
      <div className="token">#{done.token}</div>
      <p><b>{done.doctor_name}</b><br />{done.date} at {done.time}<br /><Icon name="pin" size={15} /> {done.clinic_name}</p>
      <p className="muted">Fee {money(done.fee)} · {done.payment_method === 'online' ? `Paid online (demo) · Ref ${done.payment_ref}` : 'Pay cash at the clinic'}{done.report ? ' · Report shared with the doctor' : ''}</p>
      <div className="row" style={{ justifyContent: 'center' }}>
        <button className="btn" onClick={() => nav('/appointments')}>My appointments</button>
        <button className="btn ghost" onClick={() => nav(`/messages?with=${done.doctor_user_id}`)}>Message doctor</button>
      </div>
    </div></div>
  )

  const isPatient = user?.role === 'patient'
  return (
    <div className="wrap">
      <Link to="/doctors">← All doctors</Link>
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', marginTop: '.8rem' }}>
        <div className="card">
          <div className="row"><Avatar name={doc.name} size="lg" /><div><h2 style={{ margin: 0 }}>{doc.name}</h2><span className="badge">{doc.category}</span></div></div>
          <p className="muted">{doc.qualification} · {doc.experience_years} years experience</p>
          <p>{doc.bio}</p>
          <p><b>Consultation fee:</b> {money(doc.fee)}</p>
          <h3>Clinic days</h3>
          <table><tbody>{doc.clinics.map((c, i) => <tr key={i}><td>{WD[c.weekday]}</td><td>{c.name}</td><td>{c.start_time}–{c.end_time}</td></tr>)}</tbody></table>
          {doc.is_demo ? <p className="demo">Demonstration profile.</p> : null}
        </div>
        <div className="card">
          <h3>Book an appointment</h3>
          {!isPatient && <div className="warn">{user ? 'Only patient accounts can book.' : <>Please <Link to="/login" state={{ from: `/doctors/${id}` }}>log in as a patient</Link> to book.</>}</div>}
          <label style={{ marginTop: 0 }}>1. Choose a day</label>
          <Calendar days={days} value={date} onPick={setDate} />
          {day?.working && !day.cancelled && (<>
            <p className="muted"><Icon name="pin" size={15} /> Location on this day: <b>{day.clinic?.name}</b></p>
            <label>2. Choose a time</label>
            <div className="slots">{day.slots.map((s) => <button key={s.time} className={`slot ${time === s.time ? 'on' : ''}`} disabled={!s.free} onClick={() => setTime(s.time)} title={s.free ? '' : s.past ? 'Time passed' : 'Already booked'}>{s.time}</button>)}</div>
            {day.slots.every((s) => !s.free) && <p className="muted">No free slots left on this day.</p>}
            <label>Reason for visit (optional)</label><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. HbA1c follow-up" />
            {saved && isPatient && (
              <label style={{ display: 'flex', gap: '.5rem', alignItems: 'center', fontWeight: 500, color: 'var(--ink)', background: '#f3fbfa', border: '1px solid #cfe6e4', borderRadius: 10, padding: '.6rem .7rem' }}>
                <input type="checkbox" style={{ width: 'auto' }} checked={attach} onChange={(e) => setAttach(e.target.checked)} />
                <span>Share my analysed report with the doctor ({summarize(saved.values).total} values, {summarize(saved.values).attention} need attention)</span>
              </label>)}
            <label>Payment</label>
            <div className="row">
              <label style={{ margin: 0 }}><input type="radio" style={{ width: 'auto' }} checked={pay === 'cash'} onChange={() => setPay('cash')} /> Cash at clinic</label>
              <label style={{ margin: 0 }}><input type="radio" style={{ width: 'auto' }} checked={pay === 'online'} onChange={() => setPay('online')} /> Pay online (demo)</label>
            </div>
            {pay === 'online' && <div className="card" style={{ marginTop: '.6rem', background: '#f8fbfb' }}>
              <div className="demo">Simulated payment — no real money is charged. No real card details are needed.</div>
              <label>Card number</label><input value={card.number} onChange={(e) => setCard({ ...card, number: e.target.value })} />
              <label>Name on card</label><input value={card.name} onChange={(e) => setCard({ ...card, name: e.target.value })} />
            </div>}
          </>)}
          <Err text={error} />
          <button className="btn amber block" style={{ marginTop: '1rem' }} disabled={!isPatient || !time || busy} onClick={book}>
            {busy ? 'Booking…' : time ? `Confirm ${date} ${time} · ${pay === 'online' ? 'Pay ' + money(doc.fee) : 'pay at clinic'}` : 'Select a day and time'}
          </button>
        </div>
      </div>
    </div>
  )
}
