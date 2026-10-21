// Flow 11: Admin Tonight (FR-6, FR-21). Key moment 4.
import { screen, nav, matchList, chip, btn, actions, group, item, disc, overline, teamLine, section } from '../ui.mjs';

export const ADMIN_BADGES = { Requests: 3 };

// The at-risk match card: both teams' readiness and paid state, plus the decision.
export const atRiskCard = (o = {}) => matchList({
  kicker: 'Div 2 · Pitch 3', chip: chip('pending', 'At risk'), home: 'Red Lions', away: 'Old Boys', time: '19:40',
  extra: `<hr class="la-divider" style="margin:6px 0">
${teamLine('Red Lions', '5 of 5', chip('confirmed', 'Paid'))}
${teamLine('Old Boys', 'R 210 of R 350', chip('pending', 'Unpaid'))}
<p class="body" style="margin-top:4px">${o.copy || 'Old Boys missed the T-6h payment check. You decide if they play.'}</p>
${o.actions === false ? '' : `<div class="la-actions" style="margin-top:4px">${btn('Mark paid (cash)', { kind: 'secondary', sm: true, style: 'padding:0 8px' })}${btn('Rule out', { kind: 'danger', sm: true })}</div>`}`,
});

export const timelineRows = () => group([
  item({ lead: '<span class="la-item__time">18:20</span>', title: 'Sharks vs Gunners', sub: 'Pitch 1 · Div 2 · both paid', trail: chip('confirmed', 'Ready') }),
  item({ lead: '<span class="la-item__time">18:20</span>', title: 'United vs Rangers', sub: 'Pitch 3 · Div 1 · both paid', trail: chip('confirmed', 'Ready') }),
  item({ lead: '<span class="la-item__time">19:00</span>', title: 'Wanderers vs Hammers', sub: 'Pitch 2 · Div 2 · both paid', trail: chip('confirmed', 'Ready') }),
], 'Tonight by pitch');

export function flow11() {
  const tonight = {
    id: 'f11-tonight', name: 'Tonight (Admin) — 1 match at risk', frs: ['FR-5', 'FR-6', 'FR-21'], km: 4,
    note: 'Opened at 13:45, just after the T-6h check. At-risk matches sit on top; the money row opens Finances.',
    html: screen({
      time: '13:45',
      nav: nav({ kicker: 'Tuesday 27 Oct · Nadia Pillay', title: 'Tonight' }),
      body: `${group([item({ lead: disc('neutral', 'cash'), title: 'R 2,660 of R 2,800 in', sub: "Div 2 league fees tonight · Finances", chevron: true })])}
${overline('At risk · 1')}
${atRiskCard()}
${overline('By pitch and time')}
${timelineRows()}`,
      tab: ['admin', 'Tonight', ADMIN_BADGES],
    }),
  };
  return { tonight };
}
