import type { CSSProperties } from "react";
import { existsSync } from "node:fs";
import { join } from "node:path";
import Link from "next/link";
import { BUILT, CAPABILITIES, FAQS, SAMPLE, STEPS } from "./content";
import { getWhatsAppHref } from "./lib/whatsapp";
import { ConnectCard } from "./components/connect-card";
import { HeroReceipt } from "./components/hero-receipt";
import { SiteFooter } from "./components/site-footer";
import { SiteHeader } from "./components/site-header";
import { WhatsAppButton } from "./components/whatsapp-button";

const d = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;

export default function Home() {
  const href = getWhatsAppHref();
  const hasVideo = existsSync(join(process.cwd(), "public", "demo.mp4"));
  const showVideoSlot = hasVideo || process.env.NODE_ENV !== "production";

  return (
    <>
      <SiteHeader href={href} />
      <ConnectCard whatsappHref={href} />

      <main id="main">
        <section className="hero">
          <div className="wrap hero__in">
            <div className="hero__copy">
              <p className="eyebrow" data-reveal>
                Swiggy Instamart · inside WhatsApp
              </p>
              <h1 className="hero__title" data-reveal style={d(60)}>
                Text the list. <em>We’ll handle the rest.</em>
              </h1>
              <p className="hero__support" data-reveal style={d(120)}>
                Grocer turns a message into a live Instamart basket: real prices,
                real stock, no new app.
              </p>

              <div className="hero__actions" data-reveal style={d(180)}>
                <WhatsAppButton href={href} />
                {hasVideo ? (
                  <a className="hero__demo-link" href="#demo">
                    Watch the 40-second demo
                  </a>
                ) : null}
              </div>

              {!href ? (
                <p className="button-note">
                  The WhatsApp link is not configured on this deployment.
                </p>
              ) : null}

              <p className="hero__micro" data-reveal style={d(240)}>
                <span>Early access</span>
                <span>No new app</span>
                <span>No Grocer fee</span>
              </p>
              <p className="hero__status" data-reveal style={d(280)}>
                Payments open soon. The chat is live today.
              </p>
            </div>

            <div data-reveal style={d(200)}>
              <HeroReceipt hasVideo={hasVideo} showVideoSlot={showVideoSlot} />
            </div>
          </div>
        </section>

        <section className="section section--surface" id="what">
          <div className="wrap">
            <div className="section-head">
              <div>
                <p className="kicker" data-reveal>
                  What it does
                </p>
                <h2 className="section-title" data-reveal style={d(60)}>
                  Six jobs. One chat.
                </h2>
              </div>
              <p className="lead" data-reveal style={d(120)}>
                Every row tells you where it stands: live today, in testing, or
                opening next.
              </p>
            </div>

            <ol className="jobs" data-reveal style={d(160)}>
              {CAPABILITIES.map((item, index) => (
                <li className="job" key={item.name}>
                  <span className="job__idx">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="job__name">{item.name}</h3>
                  <p className="job__line">{item.line}</p>
                  <span className="pill" data-tone={item.tone}>
                    {item.status}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="section section--dark" id="safety">
          <div className="wrap safety">
            <div className="safety__copy">
              <p className="kicker" data-reveal>
                Safety
              </p>
              <h2 className="safety__title" data-reveal style={d(60)}>
                One tap. Three checks.
              </h2>
              <p className="safety__lead" data-reveal style={d(120)}>
                No order leaves the chat until you press Pay. Even then, Grocer
                looks twice before a rupee moves.
              </p>

              <ol className="steps" data-reveal style={d(160)}>
                {STEPS.map((step, index) => (
                  <li className="step" key={step.title}>
                    <span className="step__n">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="step__title">{step.title}</h3>
                      <p className="step__body">{step.body}</p>
                    </div>
                  </li>
                ))}
              </ol>

              <p className="cap-note" data-reveal>
                <strong>₹1,000 safety cap.</strong> Baskets over ₹1,000 wait for
                you to raise the cap.
              </p>
            </div>

            <div className="paycard" data-reveal style={d(120)}>
              <div className="paycard__head">
                <h3>Checkout</h3>
                <span>Sample · {SAMPLE.count}</span>
              </div>

              <div className="paycard__lines">
                <div className="payline">
                  <span>Item total</span>
                  <span>{SAMPLE.itemTotal}</span>
                </div>
                <div className="payline payline--save">
                  <span>{SAMPLE.couponLabel}</span>
                  <span>{SAMPLE.couponAmount}</span>
                </div>
                <div className="payline">
                  <span>Handling</span>
                  <span>{SAMPLE.handling}</span>
                </div>
                <div className="payline">
                  <span>Delivery</span>
                  <span>{SAMPLE.delivery}</span>
                </div>
                <div className="payline payline--total">
                  <span>To pay</span>
                  <strong>{SAMPLE.toPay}</strong>
                </div>
              </div>

              <div className="capmeter">
                <div className="capmeter__row">
                  <span>Safety cap</span>
                  <span>{SAMPLE.capLabel}</span>
                </div>
                <div className="capmeter__track">
                  <div
                    className="capmeter__fill"
                    style={{ width: SAMPLE.capWidth }}
                  />
                </div>
              </div>

              <button className="paycard__button" type="button" disabled>
                Pay {SAMPLE.toPay}
              </button>
              <p className="paycard__note">
                The only button that can place an order.
              </p>
              <div className="paycard__foot">
                <span>Prices read at tap time</span>
                <span>UPI on Swiggy</span>
              </div>
              <span className="paycard__sample">
                Sample checkout · no payment taken
              </span>
            </div>
          </div>
        </section>

        <section className="section" id="built">
          <div className="wrap">
            <div className="section-head">
              <div>
                <p className="kicker" data-reveal>
                  Built
                </p>
                <h2 className="section-title" data-reveal style={d(60)}>
                  Wired to the real shelf.
                </h2>
              </div>
              <p className="lead" data-reveal style={d(120)}>
                Live answers come from Swiggy’s official Instamart tools, not a
                saved script.
              </p>
            </div>

            <div className="built-grid" data-reveal style={d(160)}>
              {BUILT.map((item, index) => (
                <article className="built" key={item.title}>
                  <div className="built__top">
                    <span className="built__idx">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {"big" in item ? (
                      <span className="built__big">
                        {item.big}{" "}
                        <span className="built__unit">tools</span>
                      </span>
                    ) : null}
                  </div>
                  <h3 className="built__title">{item.title}</h3>
                  <p className="built__body">{item.body}</p>
                </article>
              ))}
            </div>

            <p className="built-note" data-reveal>
              <span>224 automated tests pass.</span>
              <Link className="text-link" href="/proof">
                Read the run log
              </Link>
            </p>
          </div>
        </section>

        <section className="section section--surface" id="faq">
          <div className="wrap faq">
            <div>
              <p className="kicker" data-reveal>
                FAQ
              </p>
              <h2 className="section-title" data-reveal style={d(60)}>
                Good to know.
              </h2>
              <p className="lead" data-reveal style={d(120)}>
                Short answers on Swiggy, money and data.
              </p>
            </div>

            <div className="faq-list" data-reveal style={d(160)}>
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
      </main>

      <SiteFooter href={href} />
    </>
  );
}
