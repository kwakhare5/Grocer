import { LIVE_RECEIPT } from "../content";
import { LogoMark } from "./logo";

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m14.5 5-7 7 7 7" />
    </svg>
  );
}

function VideoIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="6.5" width="12" height="11" rx="2.5" />
      <path d="m15 10.5 6-3v9l-6-3" />
    </svg>
  );
}

function CallIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M7.5 3.5 10 8l-2 2c1.3 2.6 3.4 4.7 6 6l2-2 4.5 2.5-1.5 4c-8.5-1-14.5-7-15.5-15.5Z" />
    </svg>
  );
}

function SignalIcon() {
  return (
    <svg viewBox="0 0 16 12" width="15" height="11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <path d="M1.5 10.5V9M5.5 10.5V6.5M9.5 10.5V4M13.5 10.5V1.5" />
    </svg>
  );
}

function WifiIcon() {
  return (
    <svg viewBox="0 0 16 12" width="15" height="11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <path d="M1.5 4a10 10 0 0 1 13 0M4 6.6a6.5 6.5 0 0 1 8 0M6.6 9.2a3 3 0 0 1 2.8 0" />
      <circle cx="8" cy="10.8" r=".8" fill="currentColor" stroke="none" />
    </svg>
  );
}

function BatteryIcon() {
  return (
    <svg viewBox="0 0 22 12" width="20" height="11" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <rect x="1" y="1.5" width="17" height="9" rx="2" />
      <path d="M20 4.5v3" strokeLinecap="round" />
      <rect x="3" y="3.5" width="12" height="5" rx="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ProductDemo() {
  return (
    <figure className="phone-demo">
      <div
        className="phone"
        role="img"
        aria-label="Sample WhatsApp chat: milk, eggs and bread added to a basket. To pay ₹187."
      >
        <div className="phone__status">
          <span>10:24</span>
          <span className="phone__status-icons">
            <SignalIcon />
            <WifiIcon />
            <BatteryIcon />
          </span>
        </div>

        <div className="phone__head">
          <span className="phone__back">
            <BackIcon />
          </span>
          <span className="phone__avatar">
            <LogoMark />
          </span>
          <div className="phone__who">
            <p className="phone__name">Grocer</p>
            <p className="phone__online">online</p>
          </div>
          <span className="phone__head-icons">
            <VideoIcon />
            <CallIcon />
          </span>
        </div>

        <div className="phone__body">
          <p className="phone__date">Today</p>

          <p className="wa-bubble wa-bubble--bot">
            Hi. What do you need from Instamart?
          </p>
          <p className="wa-bubble wa-bubble--user">{LIVE_RECEIPT.user}</p>

          <div className="wa-receipt">
            <p className="wa-receipt__title">Added to your basket</p>
            <p className="wa-receipt__count">
              Your Basket ({LIVE_RECEIPT.items.length} items)
            </p>
            <ul className="wa-receipt__lines">
              {LIVE_RECEIPT.items.map((item) => (
                <li key={item.name}>
                  <span>
                    ＋ {item.name} <i>x{item.qty}</i>
                  </span>
                  <span>{item.price}</span>
                </li>
              ))}
            </ul>
            <p className="wa-receipt__total">
              <span>To Pay</span>
              <strong>{LIVE_RECEIPT.toPay}</strong>
            </p>
          </div>
        </div>

        <div className="phone__input">
          <span>Message</span>
          <span className="phone__send">↑</span>
        </div>
        <span className="phone__home" />
      </div>

      <figcaption className="phone-demo__caption">Sample</figcaption>
    </figure>
  );
}
