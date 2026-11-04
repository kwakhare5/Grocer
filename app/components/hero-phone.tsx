import { CHAT } from "../content";

export function HeroPhone() {
  return (
    <div className="phone-stage">
      <div
        className="phone"
        role="img"
        aria-label="Sample chat: a customer asks for milk, eggs, bread and paneer, and Grocer builds a ₹312 basket."
      >
        <div className="phone__screen">
          <div className="phone__bar" aria-hidden="true">
            <span className="phone__time">9:41</span>
            <span className="phone__signal">
              <i />
              <i />
              <i />
            </span>
          </div>

          <div className="phone__head">
            <span className="phone__avatar" aria-hidden="true">
              G
            </span>
            <div>
              <p className="phone__name">Grocer</p>
              <p className="phone__sub">Instamart on WhatsApp</p>
            </div>
            <span className="phone__sample">Sample</span>
          </div>

          <div className="phone__chat">
            <p className="bubble bubble--bot">{CHAT.hello}</p>
            <p className="bubble bubble--user">{CHAT.list}</p>
            <p className="bubble bubble--bot">{CHAT.found}</p>

            <div className="minibasket">
              <div className="minibasket__head">
                <span>Your basket</span>
                <span>4 items</span>
              </div>
              <ul className="minibasket__lines">
                {CHAT.basket.map((item) => (
                  <li key={item.name}>
                    <span>
                      {item.name} <span className="minibasket__qty">{item.qty}</span>
                    </span>
                    <span>{item.price}</span>
                  </li>
                ))}
              </ul>
              <div className="minibasket__total">
                <span>To pay</span>
                <strong>{CHAT.toPay}</strong>
              </div>
              <span className="minibasket__pay">Pay {CHAT.toPay}</span>
            </div>

            <p className="bubble bubble--bot">{CHAT.ready}</p>
          </div>

          <div className="phone__input" aria-hidden="true">
            <span>Message</span>
            <span className="phone__send">↑</span>
          </div>
        </div>
      </div>
      <span className="phone-stage__tag">Sample chat · nothing ordered</span>
    </div>
  );
}
