// PaymentTicket (design/src/ds/README.md): the Payment Barcode pass. Always ticket white
// with ticket ink, whatever the theme ("the ticket is sacred"). The barcode is a real
// Code 128 of the code printed under it, so the gate can scan it or type it in.

import { code128Bars } from "./code128";
import { Icon } from "./Icon";

type Props = {
  /** What it is for: "Tue 27 Oct · 19:40 · Pitch 3". */
  kicker: string;
  team: string;
  /** "Paid · valid for this match only". */
  status: string;
  /** The code as stored ("RK27104419") and as printed ("RK 2710 4419"). */
  code: string;
  displayCode: string;
};

export function PaymentTicket({ kicker, team, status, code, displayCode }: Props) {
  const { bars, width } = code128Bars(code);
  return (
    <section className="la-ticket" aria-label="Payment Barcode">
      <div className="la-ticket__head">
        <p className="la-overline">{kicker}</p>
        <div className="la-ticket__team">{team}</div>
        <div className="la-ticket__status">
          <Icon name="check" />
          {status}
        </div>
      </div>
      <div className="la-ticket__cut">
        <span className="la-ticket__notch la-ticket__notch--left" />
        <span className="la-ticket__notch la-ticket__notch--right" />
      </div>
      <div className="la-ticket__code">
        <svg
          viewBox={`0 0 ${width} 96`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Barcode ${displayCode}`}
          fill="currentColor"
          shapeRendering="crispEdges"
        >
          {bars.map((bar) => (
            <rect key={bar.x} x={bar.x} y={0} width={bar.width} height={96} />
          ))}
        </svg>
        <div className="la-ticket__num">{displayCode}</div>
      </div>
    </section>
  );
}
