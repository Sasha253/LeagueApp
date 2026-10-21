// Flow 2: Player confirmation at T-36h (FR-1 to FR-3). Key moment 1.
import { screen, nav, lockScreen, matchHero, matchList, confCard, answeredCard, squad, chip, btn, actions, group, item, disc, choice, choices, overline, banner, icon } from '../ui.mjs';

const KICK = 'Tuesday · Div 2 · Pitch 3';
const reply = (a = "I'm in", b = "Can't make it") => actions(btn(a, { ic: 'check' }), btn(b, { kind: 'secondary' }));

export function flow02() {
  const lockConfirm = {
    id: 'f02-lock', name: 'Lock screen — Confirmation', frs: ['FR-1'], km: 1, lock: 'Confirmation',
    note: 'Sent at T-36h (Mon 07:40) to every Player of both teams who opted into Tuesday Night.',
    html: lockScreen({
      time: '07:40', date: 'Monday 26 October',
      notifs: [{ title: "Can you make Tuesday's match?", body: 'Red Lions vs Old Boys · Tue 27 Oct · 19:40 · Pitch 3. Reply by Tue 13:40.', actions: ["I'm in", "Can't make it"] }],
    }),
  };

  const inbox = {
    id: 'f02-inbox', name: 'Inbox', frs: ['FR-1'], km: 1,
    html: screen({
      time: '07:41',
      nav: nav({ title: 'Inbox' }),
      body: `${choices([choice('All', true), choice('Needs reply <span class="la-choice__count">1</span>', false), choice('Updates', false)])}
${overline('Needs reply')}
${group([item({ lead: disc('pending', 'bell'), title: "Can you make Tuesday's match?", sub: 'Red Lions vs Old Boys · 19:40 · Pitch 3', below: chip('pending', 'Reply by Tue 13:40'), chevron: true })])}
${overline('Earlier')}
${group([
  item({ lead: disc('info', 'calClock'), title: 'Red Lions vs Sharks moved', sub: 'Update · now Tue 3 Nov, 20:20, Pitch 1', chevron: true }),
  item({ lead: disc('neutral', 'bell'), title: 'Tonight: Red Lions vs Gunners', sub: 'Reminder · Tue 20 Oct · 19:00 · Pitch 2', chevron: true }),
  item({ lead: disc('confirmed', 'check'), title: "You're in for Tue 20 Oct", sub: 'Confirmation · answered Mon 19 Oct', chevron: true }),
])}`,
      tab: ['player', 'Inbox', { Inbox: 1 }],
    }),
  };

  const detail = {
    id: 'f02-card', name: 'Confirmation', frs: ['FR-1', 'FR-38'], km: 1,
    note: 'The push opens straight here. Squad progress lets the Player see who has replied (FR-38).',
    html: screen({
      time: '07:41',
      nav: nav({ back: 'Inbox' }),
      body: `${matchHero({ kicker: KICK, chip: chip('pending', 'Reply needed'), home: 'Red Lions', away: 'Old Boys', time: '19:40', date: 'Tue 27 Oct', meta: [['users', '3 of 5 in'], ['card', 'R 70 each']] })}
${squad({ n: 3, min: 5, size: 7, chip: chip('pending', 'Short 2'), hint: 'Thabo, Jason and Lerato are in. 2 more needed by Tue 13:40.' })}`,
      bottom: confCard({ tone: 'pending', ic: 'bell', title: "Can you make Tuesday's match?", detail: 'Reply by Tue 13:40. You can change your answer until then.', actions: reply() }),
      bottomPlain: true,
      tab: ['player', 'Inbox', { Inbox: 1 }],
    }),
  };

  const youreIn = {
    id: 'f02-in', name: "You're in!", frs: ['FR-1', 'FR-3', 'FR-38'], km: 1,
    note: 'The single scale-in check moment (fade with Reduce Motion). The answer collapses into a chip with "Change" until the T-6h cutoff (FR-3).',
    html: screen({
      time: '07:42',
      nav: nav({ back: 'Inbox' }),
      body: `<div class="la-hero">${disc('confirmed', 'check', true)}<h1 class="title-1">You're in!</h1><p class="body muted">Red Lions vs Old Boys · Tue 27 Oct · 19:40 · Pitch 3</p></div>
${squad({ n: 4, min: 5, size: 7, hint: 'Your team needs 1 more by Tue 13:40 or the match is cancelled.' })}
${answeredCard({ title: 'Tue vs Old Boys', sub: 'Answered just now', chip: chip('confirmed', "You're in") })}`,
      bottom: `${btn('Pay R 70', { block: true, ic: 'card' })}<p class="caption muted" style="text-align:center">Your team must be paid by Tue 13:40. You can also pay cash to the club.</p>`,
      tab: ['player', 'Inbox'],
    }),
  };

  return { lockConfirm, inbox, detail, youreIn };
}
