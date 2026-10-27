// League App UI helpers. Design-system components (la-*) follow the markup of
// each component's preview.html; proposed components are marked as such.

// Lucide outline icons, 24px, 2px stroke. Paths marked (DS) are copied from the
// design-system previews; the rest are standard Lucide paths.
export const ICONS = {
  ball: '<circle cx="12" cy="12" r="9"/><path d="m12 7 4 3-1.5 4.5h-5L8 10z"/>', // (DS)
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.6c2 .7 3.2 2.6 3.5 5.4"/>', // (DS)
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0"/>', // (DS)
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4.5-6 8-6s7 2 8 6"/>', // (DS)
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>', // (DS)
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10"/>', // (DS)
  check: '<path d="M20 6 9 17l-5-5"/>', // (DS)
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', // (DS)
  x: '<path d="M18 6 6 18M6 6l12 12"/>', // (DS)
  card: '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 10h19"/>', // (DS)
  pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>', // (DS)
  hand: '<path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8a8 8 0 0 0 16 0v-3a2 2 0 0 0-4 0"/>', // (DS)
  shirt: '<path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/>',
  ticket: '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2M13 17v2M13 11v2"/>',
  calClock: '<path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5"/><path d="M16 2v4M8 2v4M3 10h5"/><path d="M17.5 17.5 16 16.3V14"/><circle cx="16" cy="16" r="6"/>',
  chevL: '<path d="m15 18-6-6 6-6"/>',
  chevR: '<path d="m9 18 6-6-6-6"/>',
  chevD: '<path d="m6 9 6 6 6-6"/>',
  arrowR: '<path d="M5 12h14M12 5l7 7-7 7"/>',
  plus: '<path d="M5 12h14M12 5v14"/>',
  minus: '<path d="M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5M12 3v12"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/>',
  sheet: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h2M14 13h2M8 17h2M14 17h2"/>',
  sliders: '<path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2m-7.07-17.07 1.41 1.41m11.32 11.32 1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  phone: '<rect width="14" height="20" x="5" y="2" rx="2"/><path d="M12 18h.01"/>',
  torch: '<path d="M18 6c0 2-2 2-2 4v10a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V10c0-2-2-2-2-4V2h12z"/><path d="M6 6h12M12 12v.01"/>',
  keyboard: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/>',
  cash: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
  wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  compare: '<path d="m16 3 4 4-4 4M20 7H4M8 21l-4-4 4-4M4 17h16"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  wifiOff: '<path d="M12 20h.01M8.5 16.43a5 5 0 0 1 7 0M5 12.86a10 10 0 0 1 5.17-2.69M19 12.86a10 10 0 0 0-2-1.52M2 8.82a15 15 0 0 1 4.18-2.64M22 8.82a15 15 0 0 0-11.29-3.76M2 2l20 20"/>',
  userPlus: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  pause: '<circle cx="12" cy="12" r="9"/><path d="M10 15V9M14 15V9"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="m5.7 5.7 12.6 12.6"/>',
  receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8M12 17.5v-11"/>',
  chart: '<path d="M12 20V10M18 20V4M6 20v-4"/>',
  mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  logo: '<path d="M4.5 19.5h4.6l3.7-15H8.2zM11.1 19.5h4.6l3.7-15h-4.6z" fill="currentColor" stroke="none"/>',
  edit: '<path d="M21.17 6.81a1 1 0 0 0-3.99-3.99L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
};

export function icon(name, o = {}) {
  const p = ICONS[name];
  if (!p) throw new Error(`Unknown icon: ${name}`);
  const size = o.size ? ` width="${o.size}" height="${o.size}"` : '';
  const a11y = o.label ? `role="img" aria-label="${o.label}"` : 'aria-hidden="true"';
  const style = o.style ? ` style="${o.style}"` : '';
  return `<svg viewBox="0 0 24 24"${size}${style} fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${a11y}>${p}</svg>`;
}

// ---------- Design-system components ----------

// StatusChip: icon plus word, never colour alone. Screen readers hear "Status: …".
const CHIP_ICON = { confirmed: 'check', pending: 'clock', cancelled: 'x', info: 'calendar' };
export const chip = (status, text) =>
  `<span class="la-chip la-chip--${status}"><span class="sr-only">Status: </span>${icon(CHIP_ICON[status])}${text}</span>`;

// Button: primary / secondary / quiet / danger, optional sm and block.
export function btn(label, o = {}) {
  const cls = ['la-btn', `la-btn--${o.kind || 'primary'}`, o.block && 'la-btn--block', o.sm && 'la-btn--sm'].filter(Boolean).join(' ');
  const attrs = [o.disabled && ' disabled', o.aria && ` aria-label="${o.aria}"`, o.style && ` style="${o.style}"`].filter(Boolean).join('');
  return `<button class="${cls}"${attrs}>${o.ic ? icon(o.ic) : ''}${label}</button>`;
}
export const actions = (a, b) => `<div class="la-actions">${a}${b}</div>`;

const metaRow = (meta = []) => meta.map(([i, t]) => `<span>${icon(i)}${t}</span>`).join('');

// MatchCard, hero variant (reply actions, scoreboard time).
export function matchHero(o) {
  return `<article class="la-card" style="display:grid;gap:12px">
<div class="la-row"><p class="la-overline">${o.kicker}</p>${o.chip || ''}</div>
<h3 class="la-fixture">${o.home} <span class="la-vs">vs</span> ${o.away}</h3>
<div class="la-row" style="align-items:flex-end"><div><div class="la-time">${o.time}</div><div class="la-meta"><span>${o.date}</span></div></div>
<div class="la-meta" style="flex-direction:column;align-items:flex-end">${metaRow(o.meta)}</div></div>
${o.actions || ''}${o.deadline ? `<div class="la-meta"><span>${icon('clock')}${o.deadline}</span></div>` : ''}${o.extra || ''}
</article>`;
}

// MatchCard, list variant (time shrinks to title-2).
export function matchList(o) {
  return `<article class="la-card" style="display:grid;gap:6px${o.style ? ';' + o.style : ''}">
<div class="la-row"><p class="la-overline">${o.kicker}</p>${o.chip || ''}</div>
<div class="la-row"><h3 class="la-fixture" style="font-size:20px">${o.home} <span class="la-vs">vs</span> ${o.away}</h3><span class="la-fixture" style="font-variant-numeric:tabular-nums">${o.time}</span></div>
${o.meta ? `<div class="la-meta">${metaRow(o.meta)}</div>` : ''}${o.extra || ''}
</article>`;
}

// ConfirmationCard: icon disc + question + detail + two actions (or none for Updates).
export const disc = (tone, ic, xl) => `<span class="la-disc la-disc--${tone}${xl ? ' la-disc--xl' : ''}" aria-hidden="true">${icon(ic)}</span>`;
export function confCard(o) {
  return `<article class="la-card" style="display:grid;gap:12px">
<div style="display:flex;gap:12px">${disc(o.tone, o.ic)}<div><div class="headline">${o.title}</div><div class="body" style="color:var(--ink-muted)">${o.detail}</div></div></div>
${o.extra || ''}${o.actions || ''}
</article>`;
}
// ConfirmationCard after answering: actions collapse into a chip with a quiet "Change".
export function answeredCard(o) {
  return `<article class="la-card la-row"><div><div class="body-strong">${o.title}</div><div class="caption" style="color:var(--ink-muted)">${o.sub}</div></div><div style="display:flex;gap:4px;align-items:center;flex-wrap:nowrap">${o.chip}${o.change === false ? '' : btn('Change', { kind: 'quiet', sm: true })}</div></article>`;
}

// SquadProgress: confirmed players against the Division minimum.
export function squad(o) {
  const size = o.size || Math.max(o.n, o.min) + 2;
  const done = o.n >= o.min;
  const w = Math.min(100, (o.n / size) * 100);
  const m = (o.min / size) * 100;
  const c = o.chip !== undefined ? o.chip : done ? chip('confirmed', 'Ready') : chip('pending', `Short ${o.min - o.n}`);
  return `<div class="${o.card === false ? '' : 'la-card '}la-progress">
<div class="la-row"><span class="la-progress__label"><b>${o.n}</b> of ${o.min} confirmed${o.team ? ` · ${o.team}` : ''}</span>${c}</div>
<div class="la-progress__track" role="img" aria-label="${o.n} of ${o.min} confirmed"><div class="la-progress__fill${done ? ' la-progress__fill--done' : ''}" style="width:${w}%"></div><div class="la-progress__min" style="left:${m}%"></div></div>
${o.hint ? `<span class="la-progress__hint">${o.hint}</span>` : ''}${o.after || ''}
</div>`;
}

// PaymentProgress: team payment against the amount due, per-player rows.
export function payProgress(o) {
  const done = o.paid >= o.due;
  const w = Math.min(100, (o.paid / o.due) * 100);
  const c = o.chip !== undefined ? o.chip : done ? chip('confirmed', 'Paid') : chip('pending', `R ${o.due - o.paid} to go`);
  const rows = (o.rows || []).map((r) => `<div class="la-row body"><span>${r.name}${r.note ? ` <span class="la-progress__hint">${r.note}</span>` : ''}</span>${r.paid ? chip('confirmed', r.amt || 'R 70') : r.chip || chip('pending', 'Unpaid')}</div>`).join('');
  return `<div class="${o.card === false ? '' : 'la-card '}la-progress">
<div class="la-row"><span class="la-progress__label"><b>R ${o.paid.toLocaleString('en-US')}</b> of R ${o.due.toLocaleString('en-US')}</span>${c}</div>
<div class="la-progress__track" role="img" aria-label="R ${o.paid} of R ${o.due} paid"><div class="la-progress__fill${done ? ' la-progress__fill--done' : ''}" style="width:${w}%"></div></div>
${o.hint ? `<span class="la-progress__hint">${o.hint}</span>` : ''}
${rows ? `<hr class="la-divider" style="margin:8px 0">${rows}` : ''}${o.action || ''}
</div>`;
}

// PaymentTicket: the Payment Barcode pass. Always ticket white, whatever the theme.
export const BARCODE = '<svg viewBox="0 0 300 96" preserveAspectRatio="none" role="img" aria-label="Payment barcode" fill="currentColor"><rect x="6" y="0" width="2" height="96"/><rect x="12" y="0" width="2" height="96"/><rect x="16" y="0" width="6" height="96"/><rect x="24" y="0" width="4" height="96"/><rect x="30" y="0" width="2" height="96"/><rect x="34" y="0" width="6" height="96"/><rect x="52" y="0" width="6" height="96"/><rect x="60" y="0" width="2" height="96"/><rect x="64" y="0" width="3" height="96"/><rect x="71" y="0" width="2" height="96"/><rect x="77" y="0" width="2" height="96"/><rect x="83" y="0" width="2" height="96"/><rect x="89" y="0" width="2" height="96"/><rect x="95" y="0" width="2" height="96"/><rect x="117" y="0" width="3" height="96"/><rect x="122" y="0" width="2" height="96"/><rect x="127" y="0" width="6" height="96"/><rect x="136" y="0" width="4" height="96"/><rect x="142" y="0" width="2" height="96"/><rect x="146" y="0" width="3" height="96"/><rect x="152" y="0" width="4" height="96"/><rect x="166" y="0" width="3" height="96"/><rect x="172" y="0" width="6" height="96"/><rect x="213" y="0" width="3" height="96"/><rect x="219" y="0" width="3" height="96"/><rect x="224" y="0" width="4" height="96"/><rect x="243" y="0" width="2" height="96"/><rect x="248" y="0" width="6" height="96"/><rect x="277" y="0" width="2" height="96"/><rect x="281" y="0" width="2" height="96"/><rect x="287" y="0" width="2" height="96"/><rect x="291" y="0" width="2" height="96"/><rect x="296" y="0" width="6" height="96"/></svg>';
export function ticket(o) {
  return `<div class="la-ticket">
<div class="la-ticket__head"><p class="la-overline">${o.kicker}</p><div class="la-ticket__team">${o.team}</div>
<div style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:15px">${icon(o.used ? 'x' : 'check', { size: 20 })}${o.status}</div></div>
<div class="la-ticket__cut"><span class="la-ticket__notch" style="left:-12px"></span><span class="la-ticket__notch" style="right:-12px"></span></div>
<div class="la-ticket__code"${o.used ? ' style="opacity:.25"' : ''}>${BARCODE}<div class="la-ticket__num">${o.code}</div></div>
</div>`;
}

// FinanceSummary: four totals and the week-by-week planner.
export function financeSummary(o) {
  const weeks = o.weeks.map((w, i) => {
    const now = i + 1 === o.now;
    const got = w.got === undefined ? '' : `<div class="la-planner__got" style="height:${w.got}%"></div>`;
    return `<div class="la-planner__week${now ? ' la-planner__week--now' : ''}"><div class="la-planner__exp" style="height:${w.exp || 100}%"></div>${got}</div>`;
  }).join('');
  const axis = o.weeks.map((w, i) => `<span${i + 1 === o.now ? ' style="color:var(--ink)"' : ''}>${i + 1}</span>`).join('');
  return `<section class="la-card" style="display:grid;gap:16px" aria-label="${o.aria || 'Finances'}">
<div class="la-row"><p class="la-overline">${o.ctx}</p>${btn('Export', { kind: 'quiet', sm: true, style: 'padding:0' })}</div>
<div class="la-stats">${o.stats.map(([l, v, owed]) => `<div class="la-stat"><span class="la-stat__label">${l}</span><span class="la-stat__value${owed ? ' la-stat__value--owed' : ''}">${v}</span></div>`).join('')}</div>
<div class="la-planner">
<div class="la-planner__key"><span><i style="border:1px solid var(--line-strong)"></i>Expected</span><span><i style="background:var(--accent-ink)"></i>Received</span></div>
<div class="la-planner__bars" role="img" aria-label="${o.reading}">${weeks}</div>
<div class="la-planner__axis" aria-hidden="true">${axis}</div>
<span class="la-progress__hint">${o.reading}</span>
</div>
</section>`;
}

// TabBar: role-aware, labels always shown. Tabs exactly as Screens.md defines them.
export const TABS = {
  player: [['Matches', 'ball'], ['Teams', 'users'], ['Inbox', 'bell'], ['Profile', 'user']],
  captain: [['Matches', 'ball'], ['My team', 'users'], ['Inbox', 'bell'], ['Profile', 'user']],
  admin: [['Tonight', 'ball'], ['Fixtures', 'calendar'], ['Requests', 'bell'], ['Scan', 'scan'], ['More', 'user']],
  referee: [['Tonight', 'ball'], ['Scan', 'scan'], ['Inbox', 'bell'], ['Profile', 'user']],
  booking: [['Book', 'calendar'], ['My bookings', 'ticket'], ['Inbox', 'bell'], ['Profile', 'user']],
};
export function tabbar(role, active, badges = {}) {
  const label = { player: 'Player', captain: 'Captain', admin: 'Admin', referee: 'Referee', booking: 'Booking User' }[role];
  return `<nav class="la-tabbar" aria-label="${label}" style="flex:none">${TABS[role].map(([l, i]) => `<button class="la-tab"${l === active ? ' aria-current="page"' : ''}>${icon(i)}${l}${badges[l] ? `<span class="la-tab__badge">${badges[l]}<span class="sr-only"> unanswered</span></span>` : ''}</button>`).join('')}</nav>`;
}

// ---------- Proposed components ----------

export const iconBtn = (ic, label, o = {}) => `<button class="la-iconbtn${o.filled ? ' la-iconbtn--filled' : ''}" aria-label="${label}">${icon(ic)}</button>`;
export const group = (rows, label) => `<div class="la-group"${label ? ` role="list" aria-label="${label}"` : ''}>${rows.join('')}</div>`;
export function item(o) {
  const cls = ['la-item', o.selected && 'la-item--selected', o.compact && 'la-item--compact'].filter(Boolean).join(' ');
  return `<div class="${cls}"${o.style ? ` style="${o.style}"` : ''}>${o.lead || ''}<div class="la-item__body"><span class="${o.strong === false ? 'body' : 'body-strong'}">${o.title}</span>${o.sub ? `<span class="caption muted">${o.sub}</span>` : ''}${o.below || ''}</div>${o.trail ? `<div class="la-item__trail">${o.trail}</div>` : ''}${o.chevron ? `<span class="la-item__chev">${icon('chevR')}</span>` : ''}</div>`;
}
export const avatar = (initials) => `<span class="la-avatar" aria-hidden="true">${initials}</span>`;
export const section = (title, action = '') => `<div class="la-section"><h2 class="headline">${title}</h2>${action}</div>`;
export const overline = (t, style = '') => `<p class="la-overline"${style ? ` style="${style}"` : ''}>${t}</p>`;
export function banner(tone, ic, title, body = '', action = '') {
  return `<div class="la-banner la-banner--${tone}" role="${tone === 'cancelled' ? 'alert' : 'status'}">${icon(ic)}<div class="la-banner__body"><span class="body-strong la-banner__title">${title}</span>${body ? `<span class="body" style="font-size:15px;line-height:20px">${body}</span>` : ''}${action}</div></div>`;
}
export const choice = (label, on, o = {}) => `<button class="la-choice${o.slot ? ' la-choice--slot' : ''}" aria-pressed="${!!on}"${o.disabled ? ' disabled' : ''}${o.aria ? ` aria-label="${o.aria}"` : ''}>${on ? icon('check') : o.ic ? icon(o.ic) : ''}${label}${o.trail ? icon(o.trail) : ''}</button>`;
export const choices = (arr, style = '') => `<div class="la-choices"${style ? ` style="${style}"` : ''}>${arr.join('')}</div>`;
export const seg = (opts, sel, label = '') => `<div class="la-seg" role="tablist"${label ? ` aria-label="${label}"` : ''}>${opts.map(([l, ic], i) => `<button role="tab" aria-selected="${i === sel}">${ic ? icon(ic) : ''}${l}</button>`).join('')}</div>`;
export const radio = (on) => `<span class="la-radio${on ? ' la-radio--on' : ''}" aria-hidden="true"></span>`;
export const checkbox = (on) => `<span class="la-checkbox${on ? ' la-checkbox--on' : ''}" aria-hidden="true">${on ? icon('check') : ''}</span>`;
export function stepper(o) {
  return `<div class="la-stepper"><button class="la-stepper__btn" aria-label="${o.dec}"${o.decOff ? ' disabled' : ''}>${icon('minus')}</button><div class="la-stepper__val" aria-live="polite">${o.value}${o.unit ? `<span class="la-stepper__unit">${o.unit}</span>` : ''}</div><button class="la-stepper__btn" aria-label="${o.inc}"${o.incOff ? ' disabled' : ''}>${icon('plus')}</button></div>`;
}
export function field(o) {
  const cls = ['la-input', o.focus && 'la-input--focus', o.error && 'la-input--error', o.code && 'la-input--code', o.area && 'la-textarea'].filter(Boolean).join(' ');
  const val = o.value ? `<span>${o.value}</span>` : `<span class="la-input__ph">${o.ph || ''}</span>`;
  return `<label class="la-field">${o.label ? `<span class="la-field__label">${o.label}</span>` : ''}<span class="${cls}">${o.ic ? icon(o.ic) : ''}${val}${o.focus ? '<i class="la-input__caret"></i>' : ''}${o.trail || ''}</span>${o.error ? `<span class="la-field__error">${icon('x')}${o.error}</span>` : o.help ? `<span class="la-field__help">${o.help}</span>` : ''}</label>`;
}
export const kv = (k, v) => `<div class="la-kv body"><span>${k}</span><span>${v}</span></div>`;
export const skel = (w, h, r) => `<span class="la-skel" style="display:block;width:${w};height:${h}px${r ? `;border-radius:${r}` : ''}"></span>`;
export function emptyState(ic, line, action) {
  return `<div class="la-empty">${icon(ic)}<p class="body">${line}</p>${action || ''}</div>`;
}
export function errorState(line, sub) {
  return `<div class="la-empty" role="alert">${disc('cancelled', 'wifiOff')}<p class="body-strong">${line}</p>${sub ? `<p class="body muted" style="margin-top:-8px">${sub}</p>` : ''}${btn('Retry', { kind: 'secondary', ic: 'refresh' })}</div>`;
}
export const sheet = (content, label = '') =>
  `<div class="la-scrim"></div><div class="la-sheet" role="dialog" aria-modal="true"${label ? ` aria-label="${label}"` : ''}><span class="la-sheet__grab" aria-hidden="true"></span>${content}<div class="ab-home"><i></i></div></div>`;
export const day = (dow, d, on, o = {}) => `<button class="la-day" aria-pressed="${!!on}"${o.disabled ? ' disabled' : ''} aria-label="${o.aria || `${dow} ${d}`}"><span>${dow}</span><b>${d}</b></button>`;
export const days = (arr) => `<div class="la-days">${arr.join('')}</div>`;
export const teamLine = (name, count, c) => `<div class="la-team-line"><span class="la-team-line__name">${name}</span>${count ? `<span class="la-team-line__count">${count}</span>` : ''}${c}</div>`;

// ---------- Screen frame ----------

function statusBar(time) {
  return `<div class="ab-status" aria-hidden="true"><span>${time || ''}</span><span class="ab-status__icons">
<svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor"><rect x="0" y="8" width="3" height="4" rx="1"/><rect x="5" y="5.5" width="3" height="6.5" rx="1"/><rect x="10" y="3" width="3" height="9" rx="1"/><rect x="15" y="0" width="3" height="12" rx="1"/></svg>
<svg width="16" height="12" viewBox="0 0 16 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4.2a10 10 0 0 1 14 0M3.6 7a6.2 6.2 0 0 1 8.8 0"/><circle cx="8" cy="10" r="1.2" fill="currentColor" stroke="none"/></svg>
<svg width="27" height="13" viewBox="0 0 27 13" fill="none"><rect x="0.5" y="0.5" width="23" height="12" rx="3.5" stroke="currentColor" opacity=".5"/><rect x="2" y="2" width="16" height="9" rx="2" fill="currentColor"/><path d="M25 4.5v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity=".5"/></svg>
</span></div>`;
}

// nav({ back: 'Inbox', title, kicker, sub, actions, mid })
export function nav(o = {}) {
  const acts = o.actions ? `<div class="ab-nav__acts">${o.actions}</div>` : '';
  const kicker = o.kicker ? `<p class="la-overline">${o.kicker}</p>` : '';
  const sub = o.sub ? `<p class="body muted">${o.sub}</p>` : '';
  if (o.back) {
    const mid = o.mid ? `<span class="headline ab-nav__mid">${o.mid}</span>` : '';
    return `<header class="ab-nav"${o.title || o.kicker || o.sub ? '' : ' style="padding-bottom:8px"'}><div class="ab-nav__bar" style="position:relative">${btn(o.back, { kind: 'quiet', ic: 'chevL', aria: `Back to ${o.back}` })}${mid}${acts || '<span></span>'}</div>${kicker}${o.title ? `<h1 class="title-1">${o.title}</h1>` : ''}${sub}</header>`;
  }
  return `<header class="ab-nav ab-nav--top">${kicker}<div class="ab-nav__title"><h1 class="title-1">${o.title}</h1>${acts}</div>${sub}</header>`;
}

// screen({ theme, time, nav, body, bottom, tab: [role, active, badges], overlay, flush })
export function screen(o) {
  const hasTab = !!o.tab;
  return `<div class="ab-screen" data-theme="${o.theme || 'night'}">
${statusBar(o.time)}
${o.nav || ''}
<div class="ab-main${o.flush ? ' ab-main--flush' : ''}"${o.mainStyle ? ` style="${o.mainStyle}"` : ''}>${o.body || ''}</div>
${o.bottom ? `<div class="ab-bottom${o.bottomPlain ? ' ab-bottom--plain' : ''}">${o.bottom}</div>` : ''}
${hasTab ? tabbar(...o.tab) : ''}
<div class="ab-home${hasTab ? ' ab-home--bar' : ''}"><i></i></div>
${o.overlay || ''}
</div>`;
}

// Lock screen with League App push notifications (mock OS surface).
export function lockScreen(o) {
  const push = (n) => `<div class="la-push${n.dim ? ' la-push--dim' : ''}" role="article" aria-label="League App notification">
<div class="la-push__head"><span class="la-push__app">${icon('logo')}</span><span class="la-overline" style="flex:1">League App</span><span class="caption muted">${n.when || 'now'}</span></div>
<div class="body-strong">${n.title}</div><div class="body">${n.body}</div>
${n.actions ? `<div class="la-push__actions">${n.actions.map((a) => btn(a, { kind: 'quiet', sm: true })).join('')}</div>` : ''}
</div>`;
  return `<div class="ab-screen" data-theme="${o.theme || 'night'}">
${statusBar('')}
<div class="la-lock__top">${icon('lock')}<div class="label">${o.date}</div><div class="la-lock__clock">${o.time}</div></div>
<div class="la-lock__stack">${o.notifs.map(push).join('')}</div>
<div class="la-lock__foot" aria-hidden="true"><span class="la-iconbtn la-iconbtn--filled">${icon('torch')}</span><span class="la-iconbtn la-iconbtn--filled">${icon('scan')}</span></div>
<div class="ab-home"><i></i></div>
</div>`;
}
