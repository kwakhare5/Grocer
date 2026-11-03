import type { Metadata } from "next";
import { getWhatsAppHref } from "../lib/whatsapp";
import { SiteFooter } from "../components/site-footer";
import { SiteHeader } from "../components/site-header";

export const metadata: Metadata = {
  title: "Proof — Grocer",
  description:
    "The last recorded runs for Grocer: router accuracy, scorecards, tests, and what is still unproven.",
  alternates: { canonical: "/proof" },
  openGraph: {
    title: "Proof — Grocer",
    description:
      "The last recorded runs for Grocer, and what is still unproven.",
    url: "/proof",
  },
};

const RUNS = [
  {
    label: "Intent routing",
    result: "40/40 exact, no unsafe writes",
    date: "31 Oct 2026",
    note: "Exact capability match.",
  },
  {
    label: "Offline scorecard",
    result: "31/31",
    date: "31 Oct 2026",
    note: "Python checks with the model out of the loop.",
  },
  {
    label: "Live scorecard",
    result: "7/13 live half-run",
    date: "3 Nov 2026",
    note: "Swiggy refused cart reads and adds, asking to review the cart; the app now replies honestly instead of failing.",
  },
  {
    label: "Automated tests",
    result: "229",
    date: "3 Nov 2026",
    note: "153 offline and 76 database tests.",
  },
  {
    label: "Production code",
    result: "Backend live on Render; /health returned 200",
    date: "3 Nov 2026",
    note: "No real order placed.",
  },
  {
    label: "Landing build",
    result: "npm run build passed",
    date: "3 Nov 2026",
    note: "Types and static pages are clean.",
  },
] as const;

const NOT_PROVEN = [
  "A real order. Checkout is locked; no payment has been taken.",
  "Live tracking after a real order.",
  "Live address add and delete.",
  "The real 24-hour deletion after a full day.",
  "A live plan Add-all tap.",
  "A real phone tap on the chat button.",
  "A live Swiggy reconnect from a bot link.",
  "Choosing between two cart lines with the same name, on a handset.",
] as const;

export default function ProofPage() {
  const href = getWhatsAppHref();

  return (
    <>
      <SiteHeader href={href} />

      <main className="page" id="main">
        <div className="wrap doc">
          <div className="page__head doc__head">
            <h1 className="page__title">What is proven.</h1>
            <p className="page__lead">The recorded runs behind the site.</p>
            <p className="page__updated">
              Last updated 3 November 2026. No real order has been placed.
            </p>
          </div>

          <div className="doc__body">
            <dl className="run-log">
              {RUNS.map((run) => (
                <div className="run-row" key={run.label}>
                  <dt className="run-label">{run.label}</dt>
                  <dd className="run-result">{run.result}</dd>
                  <dd className="run-date">{run.date}</dd>
                  <dd className="run-note">{run.note}</dd>
                </div>
              ))}
            </dl>

            <div className="prose">
              <h2>Read the raw log</h2>
              <p>
                The full build log is{" "}
                <a
                  href="https://github.com/kwakhare5/Grocer/blob/main/STATUS.md"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  STATUS.md
                </a>
                . The raw run outputs live in .scratch/ and are not published.
              </p>
            </div>
          </div>

          <aside className="doc__aside">
            <p className="doc-aside__label">Not proven</p>
            <ul className="doc-aside__list">
              {NOT_PROVEN.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </aside>
        </div>
      </main>

      <SiteFooter href={href} />
    </>
  );
}
