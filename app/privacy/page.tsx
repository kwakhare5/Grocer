import type { Metadata } from "next";
import { getWhatsAppHref } from "../lib/whatsapp";
import { SiteFooter } from "../components/site-footer";
import { SiteHeader } from "../components/site-header";
import { WhatsAppButton } from "../components/whatsapp-button";

export const metadata: Metadata = {
  title: "Privacy — Grocer",
  description:
    "What Grocer keeps, how long it keeps it, and how to delete it. A plain-language privacy note.",
  alternates: { canonical: "/privacy" },
  openGraph: {
    title: "Privacy — Grocer",
    description:
      "What Grocer keeps, how long it keeps it, and how to delete it.",
    url: "/privacy",
  },
};

export default function PrivacyPage() {
  const href = getWhatsAppHref();

  return (
    <>
      <SiteHeader href={href} />

      <main className="page" id="main">
        <div className="wrap doc">
          <div className="page__head doc__head">
            <h1 className="page__title">Privacy, in plain words.</h1>
            <p className="page__lead">
              Grocer is a small independent project. It keeps as little as it
              can.
            </p>
            <p className="page__updated">Last updated 1 November 2026.</p>
          </div>

          <div className="prose doc__body">
            <h2>What Grocer keeps</h2>
            <ul>
              <li>Your WhatsApp number and display name.</li>
              <li>The messages you send to Grocer.</li>
              <li>A Swiggy OAuth token, encrypted with AES-256-GCM.</li>
              <li>A short-lived basket, plan and address copy.</li>
              <li>The map location for an address you add.</li>
              <li>Anonymous records for payments and safety.</li>
            </ul>

            <h2>How long Grocer keeps it</h2>
            <p>
              Basket and address copies are set to expire after 24 hours. Old
              sign-in links stop working and are removed. Anonymous payment
              records stay so a payment can be traced.
            </p>

            <h2>Delete it</h2>
            <p>
              Send “delete my data” in WhatsApp. Grocer deletes the Swiggy token,
              inbound messages and cached locations, clears the plan and setup
              state, and removes your name and number from the stored record. It
              cannot delete Swiggy’s own order history; that stays with Swiggy.
            </p>

            <h2>Who processes it</h2>
            <p>
              Swiggy (Instamart), Meta (WhatsApp Cloud API), Supabase (database),
              Groq (model routing), Render (backend), Vercel (website). Each has
              its own terms.
            </p>

            <h2>Contact</h2>
            <p>
              For a privacy request, send “delete my data” in WhatsApp. For
              anything else, open an issue at{" "}
              <a
                href="https://github.com/kwakhare5/Grocer/issues"
                target="_blank"
                rel="noopener noreferrer"
              >
                github.com/kwakhare5/Grocer/issues
              </a>
              .
            </p>
          </div>

          <aside className="doc__aside">
            <p className="doc-aside__label">The short version</p>
            <p className="doc-aside__body">
              Grocer keeps what it needs to answer you. Basket and address copies
              are set to expire after 24 hours.
            </p>
            <WhatsAppButton href={href} />
            <p className="doc-aside__note">
              Send “delete my data” in the chat to revoke the Swiggy link and
              delete Grocer’s copy of the conversation.
            </p>
            <a
              className="text-link"
              href="https://github.com/kwakhare5/Grocer/issues"
              target="_blank"
              rel="noopener noreferrer"
            >
              Contact
            </a>
          </aside>
        </div>
      </main>

      <SiteFooter href={href} />
    </>
  );
}
