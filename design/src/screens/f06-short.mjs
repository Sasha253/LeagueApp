// Flow 6: Captain short of players (FR-35 to FR-37, FR-38). Key moment 2.
import { screen, nav, lockScreen, matchHero, matchList, confCard, squad, chip, btn, actions, group, item, disc, avatar, overline, banner, radio, stepper, emptyState, icon, section } from '../ui.mjs';

const KICK = 'Tuesday · Div 2 · Pitch 3';

// Captain's squad list for one match (FR-38).
const squadList = (filled) => group([
  item({ lead: disc('confirmed', 'check'), title: `Confirmed · ${filled ? 5 : 4}`, sub: `Thabo (you), Kagiso, Jason, Lerato${filled ? ', Sipho (borrowed)' : ''}`, strong: true }),
  item({ lead: disc('pending', 'clock'), title: 'Waiting · 2', sub: 'Bongani, Ruan' }),
  item({ lead: disc('cancelled', 'x'), title: 'Declined · 1', sub: 'Pieter' }),
], 'Squad replies');

export function flow06() {
  const captainShort = {
    id: 'f06-short', name: 'Match detail (Captain) — short 1', frs: ['FR-5', 'FR-35', 'FR-38'], km: 2,
    note: 'T-8h. The squad list shows each reply so the Captain knows early (FR-38); the consequence leads.',
    html: screen({
      time: '11:40',
      nav: nav({ back: 'Matches' }),
      body: `${matchHero({ kicker: KICK, chip: chip('confirmed', "You're in"), home: 'Red Lions', away: 'Old Boys', time: '19:40', date: 'Today · in 8 h', meta: [['users', '4 of 5 in'], ['card', 'R 280 of R 350']] })}
${overline('Squad replies')}
${squadList(false)}`,
      mainStyle: 'gap:12px',
      bottom: `${squad({ n: 4, min: 5, size: 7, card: false, hint: 'Find 1 more by 13:40 or the match is cancelled.' })}${btn('Request a player', { block: true, ic: 'userPlus' })}`,
      tab: ['captain', 'Matches'],
    }),
  };

  const requestForm = {
    id: 'f06-form', name: 'Request a player', frs: ['FR-35', 'FR-36'], km: 2,
    note: 'Preview names exactly who is notified. Outfield requests never reach Goalkeepers and vice versa, and only Players who chose Tuesday Night.',
    html: screen({
      time: '11:41',
      nav: nav({ back: 'Match', title: 'Request a player', sub: 'Red Lions vs Old Boys · today 19:40' }),
      body: `${section('Who do you need?')}
${group([
  item({ lead: disc('info', 'shirt'), title: 'Outfield player', sub: 'Goes to outfield Players only', trail: radio(true), selected: true }),
  item({ lead: disc('neutral', 'hand'), title: 'Goalkeeper', sub: 'Goes to Goalkeepers only', trail: radio(false) }),
], 'Position')}
${section('How many?')}
${stepper({ value: 1, unit: 'player', dec: 'Fewer players', inc: 'More players', decOff: true })}
<div class="la-card stack-1">${overline('Who gets this')}<p class="headline">23 outfield Players</p><p class="body muted">On Tuesday Night, not in Red Lions or Old Boys. The first to accept joins; then the request closes.</p></div>`,
      bottom: btn('Send to 23 Players', { block: true, ic: 'send' }),
      tab: ['captain', 'Matches'],
    }),
  };

  const sent = {
    id: 'f06-sent', name: 'Request sent — waiting', frs: ['FR-35', 'FR-37'], km: 2,
    html: screen({
      time: '11:42',
      nav: nav({ back: 'Match' }),
      body: `<div class="la-hero">${disc('pending', 'clock', true)}<h1 class="title-1">Request sent</h1><p class="body muted">23 Players on Tuesday Night have your request. The first to accept joins Red Lions.</p></div>
${group([item({ lead: disc('info', 'shirt'), title: '1 outfield player', sub: 'Sent 11:42 · 0 of 1 filled', trail: chip('pending', 'Waiting') })])}
${squad({ n: 4, min: 5, size: 7, hint: 'Find 1 more by 13:40 or the match is cancelled.' })}`,
      bottom: btn('Back to match', { kind: 'secondary', block: true }),
      tab: ['captain', 'Matches'],
    }),
  };

  const lockPlayerReq = {
    id: 'f06-lock', name: 'Lock screen — Player Request (Sipho)', frs: ['FR-36'], km: 2, lock: 'Player Request',
    note: 'Sipho Dlamini plays outfield for Sharks and chose Tuesday Night, so he is eligible.',
    html: lockScreen({
      time: '11:42', date: 'Tuesday 27 October',
      notifs: [{ title: 'Red Lions need a player', body: 'Tonight 19:40 · Pitch 3 · vs Old Boys. The first to accept joins.', actions: ['Join match', 'Not tonight'] }],
    }),
  };

  const playerReq = {
    id: 'f06-req', name: 'Player Request (outside Player)', frs: ['FR-36', 'FR-37'], km: 2,
    oq: 'The PRD does not say whether a borrowed Player pays for a league match, how much, or who pays (FR-24 covers friendlies only). The card shows no cost line until this is decided.',
    html: screen({
      time: '11:43',
      nav: nav({ back: 'Inbox' }),
      body: `${matchHero({ kicker: 'Tonight · Div 2 · Pitch 3', chip: chip('pending', 'Reply needed'), home: 'Red Lions', away: 'Old Boys', time: '19:40', date: 'Today · Tue 27 Oct', meta: [['shirt', 'You play for Red Lions'], ['users', '4 of 5 in']] })}
${group([
  item({ lead: avatar('TM'), title: 'Thabo Mokoena', sub: 'Red Lions captain' }),
  item({ lead: disc('neutral', 'pin'), title: 'Pitch 3', sub: 'Tonight · kick-off 19:40' }),
])}
<p class="caption muted" style="display:flex;gap:6px">${icon('info', { size: 16 })}You see this because you play outfield on Tuesday Night.</p>`,
      bottom: confCard({ tone: 'info', ic: 'shirt', title: 'Red Lions need a player', detail: 'The first to accept joins. 1 spot left.', actions: actions(btn('Join match'), btn('Not tonight', { kind: 'secondary' })) }),
      bottomPlain: true,
      tab: ['player', 'Inbox', { Inbox: 1 }],
    }),
  };

  const joined = {
    id: 'f06-joined', name: 'Joined — playing tonight', frs: ['FR-37'], km: 2,
    html: screen({
      time: '11:43',
      nav: nav({ back: 'Inbox' }),
      body: `<div class="la-hero">${disc('confirmed', 'check', true)}<h1 class="title-1">You're playing tonight</h1><p class="body muted">You've joined Red Lions against Old Boys. Kick-off 19:40 on Pitch 3.</p></div>
${matchList({ kicker: 'Tonight · Div 2 · Pitch 3', chip: chip('confirmed', "You're in"), home: 'Red Lions', away: 'Old Boys', time: '19:40', meta: [['pin', 'Pitch 3'], ['users', '5 of 5 in']] })}
<p class="caption muted">You'll get the Reminder at 13:40 with the pitch and time.</p>`,
      bottom: btn('View match', { block: true }),
      tab: ['player', 'Inbox'],
    }),
  };

  const filled = {
    id: 'f06-filled', name: 'Match detail (Captain) — slot filled', frs: ['FR-37', 'FR-38'], km: 2,
    oq: 'The PRD does not say whether the Captain is notified when the slot fills. Shown in-app only (banner on Match detail); no push drawn.',
    html: screen({
      time: '11:44',
      nav: nav({ back: 'Matches' }),
      body: `${matchHero({ kicker: KICK, chip: chip('confirmed', "You're in"), home: 'Red Lions', away: 'Old Boys', time: '19:40', date: 'Today · in 8 h', meta: [['users', '5 of 5 in'], ['card', 'R 280 of R 350']] })}
${banner('confirmed', 'check', 'Request filled', 'Sipho Dlamini (Sharks) accepted at 11:43. The request is closed.')}
${squadList(true)}`,
      mainStyle: 'gap:12px',
      bottom: squad({ n: 5, min: 5, size: 7, card: false, hint: 'Your team meets the minimum for tonight.' }),
      tab: ['captain', 'Matches'],
    }),
  };

  const closed = {
    id: 'f06-closed', name: 'Request closed (next Player)', frs: ['FR-37'], km: 2,
    note: 'Zaid Adams taps the same push after the slot filled. Includes the Player empty state.',
    html: screen({
      time: '11:49',
      nav: nav({ back: 'Inbox' }),
      body: `${confCard({ tone: 'info', ic: 'shirt', title: 'Red Lions need a player', detail: 'Tonight 19:40 · Pitch 3 · vs Old Boys', extra: `<div class="la-row">${chip('cancelled', 'Closed')}<span class="caption muted">Filled at 11:43</span></div><p class="body">Someone accepted first, so this spot is gone.</p>` })}
${section('Games you can join')}
<div class="la-card" style="padding:0">${emptyState('ball', 'No other games on Tuesday Night right now. We\'ll notify you when one opens.', btn('Find a team', { kind: 'secondary', ic: 'search' }))}</div>`,
      tab: ['player', 'Inbox'],
    }),
  };

  return { captainShort, requestForm, sent, lockPlayerReq, playerReq, joined, filled, closed };
}
