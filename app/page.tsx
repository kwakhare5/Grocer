import type { CSSProperties } from "react";
import {
  CAP_NOTE,
  CONNECT_STEPS,
  FAQS,
  FEATURES,
  HERO,
  LIVE_RECEIPT,
  SAFETY,
  STEPS,
} from "./content";
import { getWhatsAppHref, getWhatsAppNumber } from "./lib/whatsapp";
import { ConnectCard } from "./components/connect-card";
import { ConnectForm } from "./components/connect-form";
import { DemoVideo } from "./components/demo-video";
import { FeatureMark, LockMark } from "./components/feature-mark";
import { GroceryCluster } from "./components/grocery-cluster";
import { HowRoute } from "./components/how-route";
import { Mascot } from "./components/logo";
import { ProductDemo } from "./components/product-demo";
import { SiteFooter } from "./components/site-footer";
import { SiteHeader } from "./components/site-header";
import { TryGrocer } from "./components/try-grocer";

const d = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;

const MASCOT_TONES = [
  "var(--pink)",
  "var(--blue)",
  "var(--orange)",
  "var(--green)",
  "var(--red)",
];

export default function Home() {
  const href = getWhatsAppHref();
  const whatsappNumber = getWhatsAppNumber();

  return (
    <>
      <SiteHeader href={href} />
      <ConnectCard whatsappHref={href} />

      <main id="main">
        <section className="hero">
          <div className="wrap hero__in">
            <div className="hero__copy">
              <span className="pill" data-reveal>
                <Mascot className="pill__mascot" tone="var(--pink)" />
                {HERO.badge}
              </span>
              <h1 className="hero__title" data-reveal style={d(40)}>
                {HERO.title}
              </h1>
              <p className="hero__support" data-reveal style={d(100)}>
                {HERO.support}
              </p>

              <div className="hero__actions" data-reveal style={d(160)}>
                <a className="btn btn--primary btn--lg" href="#connect">
                  Connect your Swiggy account
                </a>
                <a className="btn btn--ghost btn--lg" href="#how">
                  See how it works
                </a>
              </div>

              {href ? (
                <p className="hero__alt" data-reveal style={d(200)}>
                  Already connected?{" "}
                  <a href={href} target="_blank" rel="noopener noreferrer">
                    Open the chat
                  </a>
                </p>
              ) : null}

              <ul className="hero__micro" data-reveal style={d(240)}>
                {HERO.micro.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="hero__media" data-reveal style={d(120)}>
              <ProductDemo />
              <GroceryCluster />
            </div>
          </div>
        </section>

        <section className="connect-band" id="connect">
          <div className="wrap connect-band__in">
            <div data-reveal>
              <p className="kicker">Connect</p>
              <h2 className="h2">Connect Swiggy once. Then it’s just chat.</h2>
              <p className="lead">
                For Swiggy customers in an Instamart service area. Enter your
                number and we send a one-time Swiggy sign-in link to that
                WhatsApp.
              </p>
              <ol className="connect-steps">
                {CONNECT_STEPS.map((step, index) => (
                  <li key={step}>
                    <span className="connect-steps__n">{index + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>

            <div data-reveal style={d(80)}>
              <ConnectForm whatsappNumber={whatsappNumber} />

              {href ? (
                <>
                  <p className="connect-band__fallback">
                    Form not working?{" "}
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      Open WhatsApp directly
                    </a>
                    .
                  </p>
                  <noscript>
                    <p className="connect-band__fallback">
                      JavaScript is off.{" "}
                      <a href={href} target="_blank" rel="noopener noreferrer">
                        Open WhatsApp directly
                      </a>
                      .
                    </p>
                  </noscript>
                </>
              ) : null}
            </div>
          </div>
        </section>

        <section className="section" id="what">
          <div className="wrap">
            <div className="section-head">
              <div>
                <p className="kicker" data-reveal>
                  Features
                </p>
                <h2 className="h2" data-reveal style={d(40)}>
                  What you can do.
                </h2>
              </div>
              <p className="lead" data-reveal style={d(80)}>
                One chat for the whole grocery run.
              </p>
            </div>

            <ol className="features">
              {FEATURES.map((item, index) => (
                <li
                  className={`feature feature--${item.tone}`}
                  key={item.title}
                  data-reveal
                  style={d(index * 45)}
                >
                  <span className="feature__mark" aria-hidden="true">
                    <FeatureMark name={item.mark} className="feature__svg" />
                  </span>
                  <div>
                    <h3 className="feature__title">{item.title}</h3>
                    <p className="feature__body">{item.body}</p>
                  </div>
                </li>
              ))}
            </ol>

            <TryGrocer />
          </div>
        </section>

        <section className="section section--surface" id="how">
          <div className="wrap">
            <div className="section-head">
              <div>
                <p className="kicker" data-reveal>
                  How it works
                </p>
                <h2 className="h2" data-reveal style={d(40)}>
                  Three steps. No new app.
                </h2>
              </div>
              <p className="lead" data-reveal style={d(80)}>
                After you connect, everything happens in the chat you already
                use. Grocer reads the message, checks Swiggy, and replies with
                the result.
              </p>
            </div>

            <HowRoute />

            <ol className="steps">
              {STEPS.map((step, index) => (
                <li
                  className="step"
                  key={step.title}
                  data-reveal
                  style={d(index * 70)}
                >
                  <span className="step__n">{index + 1}</span>
                  <h3 className="step__title">{step.title}</h3>
                  <p className="step__body">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <DemoVideo />

        <section className="section section--dark" id="safety">
          <div className="wrap safety">
            <div>
              <p className="dark-kicker" data-reveal>
                <LockMark className="dark-kicker__lock" />
                Safety
              </p>
              <h2 className="dark-title" data-reveal style={d(40)}>
                One gate before money.
              </h2>
              <p className="dark-lead" data-reveal style={d(80)}>
                Grocer can fill a basket. It cannot place an order. The last step
                is three checks, and one of them is your finger.
              </p>

              <div className="safety__list" data-reveal style={d(120)}>
                {SAFETY.map((item) => (
                  <div className="safety__item" key={item.title}>
                    <span className="safety__dot" />
                    <h3>{item.title}</h3>
                    <p>{item.body}</p>
                  </div>
                ))}
              </div>

              <p className="cap-note" data-reveal>
                <strong>{CAP_NOTE.title}.</strong> {CAP_NOTE.body}
              </p>
            </div>

            <figure className="bill-figure" data-reveal style={d(120)}>
              <div className="bill" aria-hidden="true">
                <span className="bill__stamp">Sample</span>
                <p className="bill__kicker">Swiggy Instamart</p>
                <h3 className="bill__title">Bill details</h3>

                <ul className="bill__items">
                  {LIVE_RECEIPT.items.map((item) => (
                    <li className="bill__item" key={item.name}>
                      <span className="bill__qty">{item.qty}</span>
                      <span className="bill__name">{item.name}</span>
                      <span className="bill__price">{item.price}</span>
                    </li>
                  ))}
                </ul>

                <div className="bill__fees">
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

                <div className="bill__total">
                  <span>To Pay</span>
                  <strong>{LIVE_RECEIPT.toPay}</strong>
                </div>

                <span className="bill__pay">Pay {LIVE_RECEIPT.toPay}</span>
                <p className="bill__note">No payment taken.</p>
              </div>
              <figcaption className="bill__caption">
                Sample bill. No payment taken.
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="section" id="faq">
          <div className="wrap faq">
            <div>
              <p className="kicker" data-reveal>
                FAQ
              </p>
              <h2 className="h2" data-reveal style={d(40)}>
                Questions, answered.
              </h2>
              <p className="lead" data-reveal style={d(80)}>
                Short answers on Swiggy, money and data.
              </p>
            </div>

            <div className="faq-list" data-reveal style={d(120)}>
              {FAQS.map((item) => (
                <details className="faq-item" key={item.q}>
                  <summary className="faq-summary">
                    <span>{item.q}</span>
                    <span className="faq-toggle" aria-hidden="true">
                      +
                    </span>
                  </summary>
                  <p className="faq-answer">{item.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="cta">
          <div className="wrap">
            <div className="cta__panel" data-reveal>
              <div className="cta__mascots" aria-hidden="true">
                {MASCOT_TONES.map((tone) => (
                  <Mascot key={tone} tone={tone} className="cta__mascot" />
                ))}
              </div>
              <h2 className="cta__title">
                Your next grocery run is a message away.
              </h2>
              <p className="cta__body">
                Connect your Swiggy account, send your list, and watch the
                basket fill up.
              </p>
              <div className="cta__actions">
                <a className="btn btn--primary btn--lg" href="#connect">
                  Connect your Swiggy account
                </a>
              </div>
              {href ? (
                <p className="cta__alt">
                  Already connected?{" "}
                  <a href={href} target="_blank" rel="noopener noreferrer">
                    Open the chat
                  </a>
                </p>
              ) : null}
            </div>
          </div>
        </section>
      </main>

      <SiteFooter href={href} />
    </>
  );
}
