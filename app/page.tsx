import type { CSSProperties } from "react";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { FAQS, FACTS, FEATURES, HOW, SAMPLE, STEPS } from "./content";
import { getWhatsAppHref, getWhatsAppNumber } from "./lib/whatsapp";
import { ConnectCard } from "./components/connect-card";
import { ConnectForm } from "./components/connect-form";
import { HeroPhone } from "./components/hero-phone";
import { SiteFooter } from "./components/site-footer";
import { SiteHeader } from "./components/site-header";
import { WhatsAppButton } from "./components/whatsapp-button";

const d = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;

export default function Home() {
  const href = getWhatsAppHref();
  const whatsappNumber = getWhatsAppNumber();
  const hasVideo = existsSync(join(process.cwd(), "public", "demo.mp4"));

  return (
    <>
      <SiteHeader />
      <ConnectCard whatsappHref={href} />

      <main id="main">
        <section className="hero">
          <div className="wrap hero__in">
            <div className="hero__copy">
              <p className="eyebrow" data-reveal>
                Swiggy Instamart on WhatsApp
              </p>
              <h1 className="hero__title" data-reveal style={d(60)}>
                Your Swiggy Instamart, on WhatsApp.
              </h1>
              <p className="hero__support" data-reveal style={d(120)}>
                Type what you need. Grocer builds a real basket with live prices
                and stock at your store. No new app.
              </p>

              <div className="hero__actions" data-reveal style={d(180)}>
                <a className="button button--primary" href="#connect">
                  Connect your number
                </a>
                <a className="text-link" href="#how">
                  See how it works
                </a>
              </div>

              <p className="hero__micro" data-reveal style={d(240)}>
                <span>No new app</span>
                <span>No extra fee</span>
                <span>Pay in Swiggy</span>
              </p>
            </div>

            <div className="hero__media" data-reveal style={d(200)}>
              <HeroPhone />
            </div>
          </div>

          <div className="wrap built-on" data-reveal style={d(280)}>
            <span className="built-on__label">Built on</span>
            <span>Swiggy Instamart tools</span>
            <span>WhatsApp Cloud API</span>
            <span>Groq</span>
            <span>PostgreSQL</span>
            <span className="built-on__note">
              Independent app. Not an official Swiggy product.
            </span>
          </div>
        </section>

        <section className="section" id="what">
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
                One thread for the list, the basket, the address and the order.
              </p>
            </div>

            <div className="features" data-reveal style={d(160)}>
              {FEATURES.map((item) => (
                <article
                  className={`feature feature--${item.tone}${"wide" in item && item.wide ? " feature--wide" : ""}`}
                  key={item.name}
                >
                  <span className="feature__rule" aria-hidden="true" />
                  <h3 className="feature__name">{item.name}</h3>
                  <p className="feature__line">{item.line}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section section--surface" id="how">
          <div className="wrap">
            <div className="section-head">
              <div>
                <p className="kicker" data-reveal>
                  How it works
                </p>
                <h2 className="section-title" data-reveal style={d(60)}>
                  Three steps, one chat.
                </h2>
              </div>
              <p className="lead" data-reveal style={d(120)}>
                Connect once. After that, every grocery run starts in WhatsApp.
              </p>
            </div>

            <ol className="how" data-reveal style={d(160)}>
              {HOW.map((step, index) => (
                <li className={`how__item how__item--${step.tone}`} key={step.title}>
                  <span className="how__label">Step {index + 1}</span>
                  <h3 className="how__title">{step.title}</h3>
                  <p className="how__body">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="section" id="connect">
          <div className="wrap connect-section">
            <div className="connect-section__copy">
              <p className="kicker" data-reveal>
                Connect
              </p>
              <h2 className="section-title" data-reveal style={d(60)}>
                Start here, then sign in to Swiggy.
              </h2>
              <p className="lead" data-reveal style={d(120)}>
                This page starts the handshake. WhatsApp proves the number, and
                Swiggy handles the sign-in.
              </p>

              <ul className="connect-points" data-reveal style={d(160)}>
                <li>
                  <span className="connect-points__dot connect-points__dot--blue" />
                  The number you type here is not stored.
                </li>
                <li>
                  <span className="connect-points__dot connect-points__dot--purple" />
                  The code expires in 10 minutes.
                </li>
                <li>
                  <span className="connect-points__dot connect-points__dot--green" />
                  Grocer never sees your Swiggy password.
                </li>
              </ul>
            </div>

            <div data-reveal style={d(120)}>
              <ConnectForm whatsappNumber={whatsappNumber} />
            </div>
          </div>
        </section>

        {hasVideo ? (
          <section className="section section--surface" id="demo">
            <div className="wrap demo">
              <div className="demo__media" data-reveal>
                <video
                  className="demo__video"
                  controls
                  playsInline
                  preload="metadata"
                  aria-label="Grocer demo video"
                >
                  <source src="/demo.mp4" type="video/mp4" />
                </video>
              </div>

              <div className="demo__copy">
                <p className="kicker" data-reveal>
                  Demo
                </p>
                <h2 className="section-title" data-reveal style={d(60)}>
                  From hello to basket, in one chat.
                </h2>
                <p className="lead" data-reveal style={d(120)}>
                  One real chat, recorded on a real account. No mockups.
                </p>

                <ol className="demo__steps" data-reveal style={d(160)}>
                  <li>
                    <div>
                      <h3>Say what you need</h3>
                      <p>Type it like you would text a friend.</p>
                    </div>
                  </li>
                  <li>
                    <div>
                      <h3>Check your basket</h3>
                      <p>Every item, pack and fee before you pay.</p>
                    </div>
                  </li>
                  <li>
                    <div>
                      <h3>Tap to pay</h3>
                      <p>Only a button can start checkout.</p>
                    </div>
                  </li>
                </ol>
              </div>
            </div>
          </section>
        ) : null}

        <section className="section section--surface" id="safety">
          <div className="wrap safety">
            <div className="safety__copy">
              <p className="kicker" data-reveal>
                Safety
              </p>
              <h2 className="section-title" data-reveal style={d(60)}>
                One tap. Three checks.
              </h2>
              <p className="lead" data-reveal style={d(120)}>
                Grocer can fill your basket. It cannot place an order. You tap
                Pay, then Grocer checks the basket twice before any money moves.
              </p>

              <ol className="steps" data-reveal style={d(160)}>
                {STEPS.map((step) => (
                  <li className="step" key={step.title}>
                    <div>
                      <h3 className="step__title">{step.title}</h3>
                      <p className="step__body">{step.body}</p>
                    </div>
                  </li>
                ))}
              </ol>

              <p className="cap-note" data-reveal>
                <strong>₹1,000 safety cap.</strong> Raise it yourself when you
                mean it.
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

        <section className="section" id="tools">
          <div className="wrap">
            <div className="section-head">
              <div>
                <p className="kicker" data-reveal>
                  Under the hood
                </p>
                <h2 className="section-title" data-reveal style={d(60)}>
                  Twenty tools, one chat.
                </h2>
              </div>
              <p className="lead" data-reveal style={d(120)}>
                Grocer uses Swiggy’s official Instamart tools. Python holds the
                money rules. The AI only understands what you type.
              </p>
            </div>

            <div className="facts" data-reveal style={d(160)}>
              {FACTS.map((fact) => (
                <div className={`fact fact--${fact.tone}`} key={fact.label}>
                  <span className="fact__value">{fact.value}</span>
                  <span className="fact__label">{fact.label}</span>
                  <p className="fact__note">{fact.note}</p>
                </div>
              ))}
            </div>

            <p className="tools__note" data-reveal>
              Every tool is reachable from chat, or gets a clear “not
              supported”.
            </p>
          </div>
        </section>

        <section className="section section--surface" id="privacy">
          <div className="wrap privacy">
            <div className="privacy__copy">
              <p className="kicker" data-reveal>
                Privacy
              </p>
              <h2 className="section-title" data-reveal style={d(60)}>
                Your address is not our inventory.
              </h2>
              <p className="lead" data-reveal style={d(120)}>
                Grocer needs your address to show the right store. It keeps a
                copy for 24 hours, then deletes it. Send “delete my data” and
                the rest goes too.
              </p>
            </div>

            <ul className="privacy__list" data-reveal style={d(160)}>
              <li>
                <strong>Deleted in 24 hours.</strong>
                <span>Address and basket copies do not stay.</span>
              </li>
              <li>
                <strong>Your Swiggy login is protected.</strong>
                <span>The token is encrypted, never shown.</span>
              </li>
              <li>
                <strong>The number you type is not saved.</strong>
                <span>It is only used to open the WhatsApp message.</span>
              </li>
            </ul>
          </div>
        </section>

        <section className="section" id="faq">
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

        <section className="cta">
          <div className="wrap">
            <div className="cta__card" data-reveal>
              <div>
                <h2 className="cta__title">
                  Your next grocery run is a message away.
                </h2>
                <p className="cta__body">
                  Connect your number, send your list, and watch the basket fill
                  up.
                </p>
              </div>
              <div className="cta__actions">
                <a className="button button--inverse" href="#connect">
                  Connect your number
                </a>
                <WhatsAppButton href={href} />
              </div>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter href={href} />
    </>
  );
}
