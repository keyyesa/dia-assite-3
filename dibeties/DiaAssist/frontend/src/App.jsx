import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import Nav from './components.jsx'
import Home from './pages/Home.jsx'
import Login from './pages/Login.jsx'
import Doctors from './pages/Doctors.jsx'
import DoctorProfile from './pages/DoctorProfile.jsx'
import Report from './pages/Report.jsx'
import Chat from './pages/Chat.jsx'
import Appointments from './pages/Appointments.jsx'
import History from './pages/History.jsx'
import Messages from './pages/Messages.jsx'
import DoctorDashboard from './pages/DoctorDashboard.jsx'
import Admin from './pages/Admin.jsx'
import Profile from './pages/Profile.jsx'
import { Blogs, BlogPost, Contact } from './pages/Content.jsx'

function Guard({ roles, children }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="wrap">Loading…</div>
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />
  if (roles && !roles.includes(user.role)) return <div className="wrap"><div className="err">This page is for {roles.join(' / ')} accounts only.</div></div>
  return children
}

// "/" opens the login page first; a visitor who chose "Continue as guest" (or is logged in) sees the Home page.
function Entry() {
  const { user, guest, ready } = useAuth()
  if (!ready) return <div className="wrap">Loading…</div>
  return user || guest ? <Home /> : <Login />
}

export default function App() {
  const { user, guest, ready } = useAuth()
  const loc = useLocation()
  const welcome = loc.pathname === '/login' || (loc.pathname === '/' && ready && !user && !guest)
  return (
    <>
      {!welcome && <Nav />}
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route path="/login" element={<Login />} />
        <Route path="/doctors" element={<Doctors />} />
        <Route path="/doctors/:id" element={<DoctorProfile />} />
        <Route path="/blogs" element={<Blogs />} />
        <Route path="/blogs/:id" element={<BlogPost />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/report" element={<Guard><Report /></Guard>} />
        <Route path="/assistant" element={<Guard><Chat /></Guard>} />
        <Route path="/profile" element={<Guard><Profile /></Guard>} />
        <Route path="/appointments" element={<Guard roles={['patient']}><Appointments /></Guard>} />
        <Route path="/history" element={<Guard roles={['patient']}><History /></Guard>} />
        <Route path="/messages" element={<Guard roles={['patient', 'doctor']}><Messages /></Guard>} />
        <Route path="/doctor" element={<Guard roles={['doctor']}><DoctorDashboard /></Guard>} />
        <Route path="/admin" element={<Guard roles={['admin']}><Admin /></Guard>} />
        <Route path="*" element={<div className="wrap">Page not found.</div>} />
      </Routes>
    </>
  )
}
