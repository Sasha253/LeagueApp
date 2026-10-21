// Flow 13: Gate scanning (FR-23). Key moment 3.
import { screen, nav, matchList, chip, btn, actions, group, item, disc, overline, field, sheet, icon, iconBtn, BARCODE, kv, ticket } from '../ui.mjs';

const pitch3 = (o = {}) => [
  matchList({ kicker: 'Div 1 · Pitch 3', chip: chip('confirmed', 'Both paid'), home: 'United', away: 'Rangers', time: '18:20', meta: [['check', 'United paid'], ['check', 'Rangers paid']] }),
  matchList({ kicker: 'Div 1 · Pitch 3', chip: chip('confirmed', 'Both paid'), home: 'Pirates', away: 'Dynamos', time: '19:00', meta: [['check', 'Pirates paid'], ['check', 'Dynamos paid']] }),
  matchList({ kicker: 'Div 2 · Pitch 3', chip: chip('confirmed', 'Both paid'), home: 'Red Lions', away: 'Old Boys', time: '19:40', meta: [['check', 'Red Lions paid · card'], ['check', 'Old Boys paid · cash']] }),
  matchList({ kicker: 'Div 1 · Pitch 3', chip: chip('confirmed', 'Both paid'), home: 'Swallows', away: 'Arrows', time: '20:20', meta: [['check', 'Swallows paid'], ['check', 'Arrows paid']] }),
];

// Full-screen camera with framed scan area. Role decides the tab bar.
export const scanner = (role, time, overlay = '', theme = 'night') => screen({
  theme, time,
  flush: true,
  body: `<div class="la-scan">
<div class="la-scan__top">${overline('Scan a Payment Barcode', 'color:var(--ink)')}<p class="body">Hold the barcode inside the frame.</p></div>
<div class="la-scan__frame"><i class="tl"></i><i class="tr"></i><i class="bl"></i><i class="br"></i><div class="la-scan__subject">${BARCODE}<div>RL 2710 4419</div></div><span class="la-scan__line"></span></div>
<div class="la-scan__bottom">${iconBtn('torch', 'Torch', { filled: true })}${btn('Enter code instead', { kind: 'secondary', ic: 'keyboard', style: 'background:var(--surface)' })}</div>
</div>`,
  tab: [role, 'Scan', role === 'admin' ? { Requests: 3 } : {}],
  overlay,
});

export const resultPaid = (o = {}) => sheet(`<div class="la-result la-result--paid">${icon('check')}<span class="la-result__word">Paid</span></div>
<div class="stack-1"><p class="title-2">${o.team || 'Red Lions'}</p><p class="body muted">${o.match || 'vs Old Boys · 19:40 · Pitch 3'}</p></div>
<div class="stack-2">${kv('Barcode', o.code || 'RL 2710 4419')}${kv('Valid for', o.valid || 'This match only')}${kv('Paid', o.how || 'R 350 · card')}</div>
${btn('Scan next', { block: true, ic: 'scan' })}`, 'Scan result');

export const resultNotPaid = (o = {}) => sheet(`<div class="la-result la-result--notpaid">${icon('x')}<span class="la-result__word">Not paid</span></div>
<div class="stack-1"><p class="title-2">${o.team || 'Old Boys'}</p><p class="body muted">${o.match || 'vs Red Lions · 19:40 · Pitch 3'}</p></div>
<div class="stack-1"><p class="body-strong">${o.reason || 'This Barcode was for Tue 20 Oct. It is not valid tonight.'}</p><p class="body muted">${o.next || "Ask the Captain to open tonight's Barcode."}</p></div>
${actions(btn('Scan next', { ic: 'scan' }), btn('Enter code', { kind: 'secondary' }))}`, 'Scan result');

export function flow13() {
  const refTonight = {
    id: 'f13-ref-tonight', name: 'Tonight (Referee) — Pitch 3 only', frs: ['FR-23'], km: 3,
    html: screen({
      time: '19:20',
      nav: nav({ kicker: 'Tuesday 27 Oct · Pitch 3', title: 'Tonight' }),
      body: (() => { const m = pitch3(); return `${overline('Now playing')}${m[1]}${overline('Next')}${m[2]}${m[3]}`; })(),
      bottom: btn('Scan ticket', { block: true, ic: 'scan' }),
      tab: ['referee', 'Tonight'],
    }),
  };

  const refScan = {
    id: 'f13-ref-scan', name: 'Scan (Referee)', frs: ['FR-23'], km: 3,
    note: 'Camera opens directly from the Scan tab. Scan line sweeps; fades with Reduce Motion. Torch for dark gates.',
    html: scanner('referee', '19:21'),
  };

  const refPaid = {
    id: 'f13-ref-paid', name: 'Scan result — Paid', frs: ['FR-23', 'FR-20'], km: 3,
    html: scanner('referee', '19:21', resultPaid()),
  };

  const refNotPaid = {
    id: 'f13-ref-notpaid', name: 'Scan result — Not paid (wrong match)', frs: ['FR-23'], km: 3, sep: 'or',
    note: 'Barcodes are per match and cannot be reused (NFR: Barcode integrity), so an old pass reads Not paid with the reason.',
    html: scanner('referee', '19:22', resultNotPaid()),
  };

  const refManual = {
    id: 'f13-ref-manual', name: 'Enter code (fallback)', frs: ['FR-23'], km: 3,
    html: screen({
      time: '19:23',
      nav: nav({ back: 'Scan', title: 'Enter code', sub: 'Type the code printed under the barcode.' }),
      body: field({ label: 'Barcode code', value: 'RL 2710 4419', focus: true, code: true, help: '10 letters and numbers. Spaces are optional.' }),
      bottom: btn('Check code', { block: true }),
      tab: ['referee', 'Scan'],
    }),
  };

  return { refTonight, refScan, refPaid, refNotPaid, refManual, pitch3 };
}
