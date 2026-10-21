// Flow 14: Finances, phase 1 (FR-25 to FR-27, FR-47 to FR-51). Key moment 4.
import { screen, nav, financeSummary, chip, btn, group, item, disc, overline, choice, choices, section, icon, seg } from '../ui.mjs';
import { ADMIN_BADGES } from './f11-tonight.mjs';

// Spring 2026 · Tuesday · Div 2: 8 teams × R 350 × 10 weeks = R 28,000.
// Week 4: Hammers owe R 350 (cash expected at the gate, never paid). Week 7 (tonight): Old Boys owe R 140.
export const WEEKS = [100, 100, 100, 87.5, 100, 100, 95, undefined, undefined, undefined].map((got) => ({ got }));
export const SUMMARY = {
  ctx: 'Spring 2026 · Tuesday · Div 2',
  aria: 'Finances, Spring 2026, Tuesday Night, Division 2',
  stats: [['Due to date', 'R 19,600'], ['Received', 'R 19,110'], ['Outstanding', 'R 490', true], ['Season expected', 'R 28,000']],
  weeks: WEEKS, now: 7,
  reading: 'Week 7 is R 140 short; season R 490 behind.',
};

const filters = (sel = []) => choices([
  choice('Spring 2026', false, { trail: 'chevD', aria: 'Season: Spring 2026' }), choice('Tuesday', false, { trail: 'chevD', aria: 'Night: Tuesday' }), choice('Div 2', false, { trail: 'chevD', aria: 'Division: 2' }),
], 'flex-wrap:nowrap');

export const owedRow = (o) => `<div class="la-item" style="display:grid;grid-template-columns:1fr auto;gap:0 12px;padding-bottom:4px">
<div class="la-item__body"><span class="body-strong">${o.title}</span><span class="caption muted">${o.sub}</span></div>
<span class="title-2 tnum" style="color:var(--pending)">${o.amt}</span>
<div style="grid-column:1/-1;display:flex;gap:4px;margin-left:-12px">${btn('Remind', { kind: 'quiet', sm: true, ic: 'bell' })}${o.cash === false ? '' : btn('Mark cash paid', { kind: 'quiet', sm: true, ic: 'cash' })}</div>
</div>`;

export function flow14() {
  const finances = {
    id: 'f14-fin', name: 'Finances — summary and planner', frs: ['FR-25', 'FR-47'], km: 4,
    note: 'Opened from More or from the money row on Tonight. Tapping a week filters the Outstanding list to that week.',
    html: screen({
      time: '13:50',
      nav: nav({ back: 'More', title: 'Finances' }),
      body: `${filters()}
${financeSummary(SUMMARY)}`,
      tab: ['admin', 'More', ADMIN_BADGES],
    }),
  };

  const outstanding = {
    id: 'f14-owed', name: 'Finances — method split and Outstanding', frs: ['FR-25', 'FR-48'], km: 4,
    html: screen({
      time: '13:50',
      nav: nav({ back: 'More', mid: 'Finances', actions: btn('Export', { kind: 'quiet', ic: 'download' }) }),
      body: `${section('Received by method')}
<div class="la-stats"><div class="la-stat"><span class="la-stat__label">Card</span><span class="la-stat__value">R 15,960</span></div><div class="la-stat"><span class="la-stat__label">Cash</span><span class="la-stat__value">R 2,450</span></div><div class="la-stat"><span class="la-stat__label">Credit used</span><span class="la-stat__value">R 700</span></div><div class="la-stat"><span class="la-stat__label">Credit held</span><span class="la-stat__value">R 420</span></div></div>
${section('Outstanding · largest first')}
${seg([['Teams · 2'], ['Players · 2']], 0, 'Who owes')}
${group([
  owedRow({ title: 'Hammers', sub: 'Week 4 · cash expected at the gate, not received', amt: 'R 350' }),
  owedRow({ title: 'Old Boys', sub: 'Week 7 · Werner Smit and Dylan Jacobs unpaid', amt: 'R 140' }),
], 'Outstanding teams')}`,
      tab: ['admin', 'More', ADMIN_BADGES],
    }),
  };

  return { finances, outstanding, filters };
}
