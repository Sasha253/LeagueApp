// Flow 15: Booking User (FR-28 to FR-34, FR-44 to FR-46). Key moment 5.
import { screen, nav, chip, btn, actions, group, item, disc, overline, choice, day, days, radio, stepper, section, sheet, ticket, kv, icon, banner } from '../ui.mjs';

// Sample: Craig Naidoo books Pitch 1, Sat 24 Oct 10:00, 2 h at R 450/h = R 900.
// Payment cutoff 24 h before (Fri 23 Oct 10:00); 6 h before is Sat 04:00.
export const policyRows = (now, compact) => group([
  item({ title: 'Before Fri 23 Oct 10:00', sub: 'Free. Nothing is charged.', trail: now === 0 ? chip('info', 'Now') : '', selected: now === 0, strong: now === 0, compact }),
  item({ title: 'Fri 10:00 to Sat 04:00', sub: '50% back as credit', trail: now === 1 ? chip('info', 'Now') : '', selected: now === 1, strong: now === 1, compact }),
  item({ title: 'After Sat 04:00, or no-show', sub: 'No credit', trail: now === 2 ? chip('info', 'Now') : '', selected: now === 2, strong: now === 2, compact }),
], 'Cancellation policy');

export const bookingTicket = (o = {}) => ticket({ kicker: o.kicker || 'Sat 24 Oct · 10:00–12:00', team: o.team || 'Pitch 1 · 2 h', status: o.status || 'Approved · valid for this booking', code: o.code || 'BK 2410 0815', used: o.used });

export function flow15() {
  const pick = {
    id: 'f15-pick', name: 'Book a field — day, field, start', frs: ['FR-28'], km: 5,
    html: screen({
      time: '10:12',
      nav: nav({ title: 'Book a field' }),
      body: `${section('Which day?')}
${days([day('Wed', 21, false), day('Thu', 22, false), day('Fri', 23, false), day('Sat', 24, true), day('Sun', 25, false), day('Mon', 26, false)])}
${section('Which field?')}
${group([
  item({ title: 'Pitch 1', sub: '5-a-side · R 450 an hour', trail: radio(true), selected: true, compact: true }),
  item({ title: 'Pitch 2', sub: '5-a-side · R 450 an hour', trail: radio(false), compact: true }),
  item({ title: 'Pitch 4', sub: '7-a-side · R 600 an hour', trail: radio(false), compact: true }),
], 'Field')}
${section('Start time', '<span class="caption muted">Faded times are booked</span>')}
<div class="la-slots">${choice('08:00', false, { slot: true })}${choice('09:00', false, { slot: true })}${choice('10:00', true, { slot: true })}${choice('11:00', false, { slot: true })}${choice('12:00', false, { slot: true, disabled: true, aria: '12:00, booked' })}${choice('13:00', false, { slot: true, disabled: true, aria: '13:00, booked' })}${choice('14:00', false, { slot: true })}${choice('15:00', false, { slot: true })}</div>`,
      bottom: btn('Next: how long', { block: true }),
      tab: ['booking', 'Book'],
    }),
  };

  const hours = {
    id: 'f15-hours', name: 'Book a field — hours, price, policy', frs: ['FR-28', 'FR-33', 'FR-34', 'FR-45', 'FR-46'], km: 5,
    note: 'Price updates live (hourly fee × hours). Credit is used before the card (FR-46). The policy and current outcome show before confirming (FR-45).',
    html: screen({
      time: '10:13',
      nav: nav({ back: 'Book a field', kicker: 'Sat 24 Oct · Pitch 1 · from 10:00', title: 'How long?' }),
      body: `${stepper({ value: 2, unit: '10:00 to 12:00 · 12:00 is booked', dec: 'Fewer hours', inc: 'More hours', incOff: true })}
<div class="la-stats"><div class="la-stat"><span class="la-stat__label">R 450 × 2 h</span><span class="la-stat__value">R 900</span></div><div class="la-stat"><span class="la-stat__label">Your credit first</span><span class="la-stat__value">– R 225</span></div></div>
<p class="body" style="margin-top:-4px">R 675 goes on your card on <b>Fri 23 Oct 10:00</b>. Nothing is charged before then.</p>
${section('If you cancel')}
${policyRows(0, true)}`,
      bottom: btn('Request booking', { block: true }),
      tab: ['booking', 'Book'],
    }),
  };

  const requested = {
    id: 'f15-requested', name: 'Booking requested — pending', frs: ['FR-29'], km: 5,
    html: screen({
      time: '10:14',
      nav: nav({ back: 'Book a field' }),
      body: `<div class="la-hero">${disc('pending', 'clock', true)}<h1 class="title-1">Booking requested</h1><p class="body muted">The club approves every booking. Your entry Barcode appears here once it's approved.</p></div>
<div class="la-card stack-2"><div class="la-row">${overline('Sat 24 Oct · Pitch 1')}${chip('pending', 'Requested')}</div><p class="title-2 tnum">10:00–12:00</p>${kv('R 450 × 2 h', 'R 900')}${kv('Credit used', '– R 225')}${kv('Card, on Fri 23 Oct 10:00', 'R 675')}</div>`,
      bottom: btn('View my bookings', { kind: 'secondary', block: true }),
      tab: ['booking', 'Book'],
    }),
  };

  const approved = {
    id: 'f15-ticket', name: 'Booking approved — entry Barcode', frs: ['FR-30'], km: 5,
    note: 'Opening the Barcode raises brightness to maximum and keeps the screen awake; closing restores it.',
    html: screen({
      time: '12:31',
      nav: nav({ back: 'My bookings' }),
      body: `<div class="la-row">${chip('confirmed', 'Approved')}<span class="caption muted" style="display:flex;gap:4px;align-items:center">${icon('sun', { size: 16 })}Brightness at maximum</span></div>
${bookingTicket()}
<p class="caption muted" style="text-align:center">Show this at the gate. It works once, for this booking only.</p>`,
      bottom: actions(btn('Reschedule', { kind: 'secondary', ic: 'calClock' }), btn('Cancel booking', { kind: 'danger' })),
      tab: ['booking', 'My bookings'],
    }),
  };

  const cancelSheet = {
    id: 'f15-cancel', name: 'Cancel booking — outcome shown first', frs: ['FR-31', 'FR-44', 'FR-45'], km: 5,
    note: 'Fri 23 Oct 18:05: after the payment cutoff, more than 6 h before. With the gateway the policy applies automatically (FR-44).',
    html: screen({
      time: '18:05',
      nav: nav({ back: 'My bookings' }),
      body: `<div class="la-card stack-2"><div class="la-row">${overline('Sat 24 Oct · Pitch 1')}${chip('confirmed', 'Approved')}</div><p class="title-2 tnum">10:00–12:00</p>${kv('Paid on Fri 23 Oct', 'R 900')}${kv('Card', 'R 675')}${kv('Credit', 'R 225')}</div>`,
      tab: ['booking', 'My bookings'],
      overlay: sheet(`<div class="stack-2"><p class="title-2">Cancel this booking?</p><p class="body">You get <b>R 450 credit</b>, half of R 900. No card refund. The credit is used first on your next booking.</p></div>
${policyRows(1)}
${btn('Cancel booking, get R 450 credit', { kind: 'danger', block: true })}${btn('Keep booking', { kind: 'secondary', block: true })}`, 'Cancel booking'),
    }),
  };

  return { pick, hours, requested, approved, cancelSheet };
}
