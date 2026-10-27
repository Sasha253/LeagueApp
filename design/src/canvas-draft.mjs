// Draft canvas: the five key moments from Screens.md, for review before the full build.
import { chip } from './ui.mjs';
import { panel, list } from './panels.mjs';
import { flow02 } from './screens/f02-confirmation.mjs';
import { flow06 } from './screens/f06-short.mjs';
import { flow13 } from './screens/f13-scan.mjs';
import { flow11 } from './screens/f11-tonight.mjs';
import { flow14 } from './screens/f14-finances.mjs';
import { flow15 } from './screens/f15-booking.mjs';

export function canvas() {
  const f2 = flow02(), f6 = flow06(), f13 = flow13(), f11 = flow11(), f14 = flow14(), f15 = flow15();
  return {
    file: 'key-moments-draft.html',
    kicker: 'Draft 1 · key moments · Night theme · 375 × 812',
    title: 'League App — key moments',
    intro: 'The five key moments from Screens.md, built only from the League App tokens, type styles and components. Each artboard is labelled with its screen name and the FRs it covers. Sample data: Tuesday Night league, Division 2, Pitch 3, Red Lions vs Old Boys, kick-off 19:40 on Tue 27 Oct, R 70 per player, R 350 per team, minimum 5 players.',
    legend: `${chip('info', 'Key moment')}${chip('info', 'Push type')}${chip('pending', 'Open question')}<span class="caption muted">Arrows: next step. "Or": alternative state of the same step.</span>`,
    after: [
      panel('Open questions so far', list([
        'Does a borrowed Player pay for a league match, how much, and who pays? FR-24 sets a fee only for friendlies. (Player Request, key moment 2)',
        'Is the Captain notified when a Player or Goalkeeper Request fills? The PRD names no notification for it. (Match detail, slot filled)',
      ])),
      panel('Proposed components so far', '<p class="body muted" style="margin:0 0 12px">Built from existing tokens in the same style; not yet in the design system.</p>' + list([
        'ListGroup and ListRow (lead disc or avatar, title, caption, trailing chip or control)', 'Avatar (initials)', 'IconButton (48 × 48, always labelled)', 'Banner (strong colour on its -soft tint)',
        'ChoiceChip (filters, Nights, time slots, dropdown filters)', 'SegmentedControl', 'Radio and Checkbox marks', 'Stepper (people, hours)', 'TextField and code field',
        'BottomSheet with scrim', 'Status hero (large disc and title for result states)', 'Scan result panel (Paid / Not paid)', 'DayStrip date picker and slot grid',
        'Scanner viewfinder (frame, sweep line, torch)', 'EmptyState recipe', 'Lock screen and push notification (mock OS surface; app icon is the Kick-off stripes mark)',
      ], false)),
    ],
    rows: [
      { id: 'km1', kicker: 'Key moment 1 · Player', name: 'Player confirmation at T-36h', desc: 'Mon 26 Oct 07:40. Kagiso Molefe (Red Lions) gets the Confirmation, opens it from the Inbox and says he is in.', boards: [f2.lockConfirm, f2.inbox, f2.detail, f2.youreIn] },
      { id: 'km2', kicker: 'Key moment 2 · Captain and outside Player', name: 'Captain short of players at T-8h', desc: 'Tue 27 Oct 11:40. Thabo Mokoena (Red Lions captain) has 4 of 5. He requests an outfield player; Sipho Dlamini (Sharks) accepts first; Zaid Adams is too late.', boards: [f6.captainShort, f6.requestForm, f6.sent, f6.lockPlayerReq, f6.playerReq, f6.joined, f6.filled, f6.closed] },
      { id: 'km3', kicker: 'Key moment 3 · Referee', name: 'Scanning a ticket at the gate', desc: 'Tue 27 Oct 19:20. Mandla Sithole referees Pitch 3 and scans each Captain\'s Payment Barcode.', boards: [f13.refTonight, f13.refScan, f13.refPaid, f13.refNotPaid, f13.refManual] },
      { id: 'km4', kicker: 'Key moment 4 · Admin', name: 'Tonight with one match at risk, and Finances mid-season', desc: 'Tue 27 Oct 13:45, just after the T-6h check. Nadia Pillay (Tuesday Night Admin) sees Old Boys unpaid, then checks the season (week 7 of 10).', boards: [f11.tonight, f14.finances, f14.outstanding] },
      { id: 'km5', kicker: 'Key moment 5 · Booking User', name: 'Booking a field and seeing the cancellation outcome', desc: 'Wed 21 Oct 10:12. Craig Naidoo books Pitch 1 for Sat 24 Oct, gets approved, then cancels on Fri 23 Oct at 18:05.', boards: [f15.pick, f15.hours, f15.requested, f15.approved, f15.cancelSheet] },
    ],
  };
}
