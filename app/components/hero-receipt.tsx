import { SAMPLE } from "../content";

type HeroReceiptProps = {
  hasVideo: boolean;
  showVideoSlot: boolean;
};

export function HeroReceipt({ hasVideo, showVideoSlot }: HeroReceiptProps) {
  return (
    <div className="stage" id="demo">
      <article className="receipt" aria-label="Sample Instamart basket">
        <span className="stamp">Sample</span>

        <div className="receipt__head">
          <p className="receipt__brand">Grocer.</p>
          <p className="receipt__tag">Instamart basket</p>
        </div>

        <p className="receipt__msg">
          <strong>You:</strong> {SAMPLE.message}
        </p>
        <div className="receipt__meta">
          <span>{SAMPLE.time}</span>
          <span>{SAMPLE.count}</span>
        </div>

        <hr className="receipt__rule" />

        <ul className="receipt__items">
          {SAMPLE.items.map((item) => (
            <li className="receipt__line" key={item.name}>
              <span>
                {item.name}
                <span className="receipt__qty">{item.qty}</span>
              </span>
              <span>{item.price}</span>
            </li>
          ))}
        </ul>

        <hr className="receipt__rule" />

        <div className="receipt__sum">
          <span>Item total</span>
          <span>{SAMPLE.itemTotal}</span>
        </div>
        <div className="receipt__sum receipt__sum--save">
          <span>{SAMPLE.couponLabel}</span>
          <span>{SAMPLE.couponAmount}</span>
        </div>
        <div className="receipt__sum">
          <span>Handling</span>
          <span>{SAMPLE.handling}</span>
        </div>
        <div className="receipt__sum">
          <span>Delivery</span>
          <span>{SAMPLE.delivery}</span>
        </div>
        <div className="receipt__total">
          <span>To pay</span>
          <strong>{SAMPLE.toPay}</strong>
        </div>

        <p className="receipt__delivery">
          Sample basket · nothing ordered
        </p>
        <p className="receipt__foot">
          Sample prices. Chat reads your store live.
        </p>
      </article>

      {hasVideo ? (
        <div className="phone">
          <video
            className="phone__video"
            controls
            playsInline
            preload="metadata"
            aria-label="Grocer demo video"
          >
            <source src="/demo.mp4" type="video/mp4" />
          </video>
        </div>
      ) : null}

      {!hasVideo && showVideoSlot ? (
        <div className="phone" role="img" aria-label="Demo video placeholder">
          <div className="phone__screen">
            <div className="phone__play" aria-hidden="true">
              ▶
            </div>
            <p className="phone__label">Demo · 40 sec</p>
            <p className="phone__title">Your recording goes here.</p>
            <p className="phone__note">
              Add public/demo.mp4 to show one real chat, from “hi” to the basket.
            </p>
          </div>
          <div className="phone__bars" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>
        </div>
      ) : null}

      <p className="stage__caption">From message to basket</p>
    </div>
  );
}
