const P = {
  flask: 'M9 3h6M10 3v6.2L5.5 18a2 2 0 0 0 1.8 3h9.4a2 2 0 0 0 1.8-3L14 9.2V3M7.5 15h9',
  chat: 'M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z',
  steth: 'M5 3v5a4 4 0 0 0 8 0V3M9 12v3a5 5 0 0 0 10 0v-2M19 11a2 2 0 1 0 .01 0',
  calendar: 'M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z',
  bell: 'M6 9a6 6 0 1 1 12 0c0 6 2 7.5 2 7.5H4S6 15 6 9M10 20a2 2 0 0 0 4 0',
  user: 'M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8M4 21a8 8 0 0 1 16 0',
  upload: 'M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3',
  file: 'M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7zM14 3v4h4M9 13h6M9 17h4',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  alert: 'M12 8v5M12 17h.01M10.3 4.3L2.7 18a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0',
  menu: 'M4 6h16M4 12h16M4 18h16',
  x: 'M6 6l12 12M18 6L6 18',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  msg: 'M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4V6a1 1 0 0 1 1-1z',
  clock: 'M12 7v5l3 2M12 21a9 9 0 1 0 0-18a9 9 0 0 0 0 18',
  pin: 'M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11M12 12a2 2 0 1 0 0-4a2 2 0 0 0 0 4',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9c-4.5-1-8-4-8-9V6zM9 12l2 2 4-4',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
  book: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11',
  chevron: 'M6 9l6 6 6-6',
  image: 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M9 9.5h.01',
}

export function Icon({ name, size = 20, className = '', title }) {
  return (
    <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      <path d={P[name] || ''} />
    </svg>
  )
}

function cube(cx, cy, r, top, left, right) {
  const k = 0.866 * r
  const f = (pts, c, key) => (
    <polygon key={key} points={pts.map((q) => q.join(',')).join(' ')} fill={c} stroke={c} strokeWidth="2.6" strokeLinejoin="round" />
  )
  return [
    f([[cx, cy - r], [cx + k, cy - r / 2], [cx, cy], [cx - k, cy - r / 2]], top, 't'),
    f([[cx - k, cy - r / 2], [cx, cy], [cx, cy + r], [cx - k, cy + r / 2]], left, 'l'),
    f([[cx + k, cy - r / 2], [cx, cy], [cx, cy + r], [cx + k, cy + r / 2]], right, 'r'),
  ]
}

// Sugar-crystals mark: three isometric sugar cubes. `light` = brighter colours for dark backgrounds.
export function Logo({ size = 34, light = false }) {
  const c = light
    ? { a: ['#D6FBF6', '#8FEDE3', '#3FB8AE'], b: ['#BFF5EE', '#5ED3C8', '#2AA79F'] }
    : { a: ['#8FEDE3', '#19B3A8', '#0B7078'], b: ['#6FE0D5', '#14A39B', '#0A6068'] }
  return (
    <svg width={size} height={size} viewBox="0 0 80 80" aria-hidden="true" className="logo-mark">
      <g>{cube(26, 58, 17, ...c.b)}</g>
      <g>{cube(54, 58, 17, ...c.b)}</g>
      <g>{cube(40, 30, 17, ...c.a)}</g>
    </svg>
  )
}

// Divider lockup: mark | DiaAssist with "AI · Diabetes care" beneath.
export function Brand({ light = false, size = 34 }) {
  return (
    <span className={`brand-lock${light ? ' light' : ''}`}>
      <Logo size={size} light={light} />
      <span className="brand-bar" />
      <span className="brand-stack">
        <span className="brand-name">DiaAssist</span>
        <span className="brand-tag">AI · Diabetes care</span>
      </span>
    </span>
  )
}
