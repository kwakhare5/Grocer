import { LIVE_RECEIPT } from "../content";
import { LogoMark } from "./logo";

export function ProductDemo() {
  return (
    <figure className="chat-demo">
      <div className="chat-demo__frame" aria-hidden="true">
        <div className="chat-demo__head">
          <span className="chat-demo__avatar" aria-hidden="true">
            <LogoMark />
          </span>
          <div>
            <p className="chat-demo__name">Grocer</p>
            <p className="chat-demo__status">
              <span aria-hidden="true" /> online
            </p>
          </div>
        </div>

        <div className="chat-demo__body">
          <p className="wa-bubble wa-bubble--bot">
            Hi. What do you need from Instamart?
          </p>
          <p className="wa-bubble wa-bubble--user">{LIVE_RECEIPT.user}</p>

          <div className="wa-receipt">
            <p className="wa-receipt__title">Added to your basket</p>
            <p className="wa-receipt__count">Your Basket (3 items)</p>
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
            <div className="wa-receipt__fees">
              <p>
                <span>Item Total</span>
                <span>{LIVE_RECEIPT.itemTotal}</span>
              </p>
              <p>
                <span>Handling Fee</span>
                <span>{LIVE_RECEIPT.handling}</span>
              </p>
              <p>
                <span>Delivery Partner Fee</span>
                <span>{LIVE_RECEIPT.delivery}</span>
              </p>
            </div>
            <p className="wa-receipt__total">
              <span>To Pay</span>
              <strong>{LIVE_RECEIPT.toPay}</strong>
            </p>
          </div>

          <div className="wa-buttons" aria-hidden="true">
            {LIVE_RECEIPT.buttons.map((label, index) => (
              <span
                className={`wa-button${index === 0 ? " wa-button--primary" : ""}`}
                key={label}
              >
                {label}
              </span>
            ))}
          </div>
        </div>

        <div className="chat-demo__input" aria-hidden="true">
          <span>Message</span>
          <span className="chat-demo__send">↑</span>
        </div>
      </div>

      <figcaption className="chat-demo__caption">
        Example chat. No order or payment.
      </figcaption>
    </figure>
  );
}
