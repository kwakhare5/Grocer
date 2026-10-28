"use client";

import { useEffect, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Lock,
  MessageCircle,
  ShieldCheck,
  ShoppingBasket,
} from "lucide-react";

const WHATSAPP_DISPLAY = "+91 98765 43210";

function whatsappHref(): string | null {
  const number = (process.env.NEXT_PUBLIC_WHATSAPP_NUMBER || "").replace(/\D/g, "");
  if (!number) return null;
  return `https://wa.me/${number}?text=${encodeURIComponent(
    "Hi Grocer, I would like to shop groceries.",
  )}`;
}

function WhatsAppButton({ large = false }: { large?: boolean }) {
  const href = whatsappHref();
  const base = large
    ? "inline-flex items-center justify-center gap-2 rounded-xl px-7 py-4 text-base font-semibold"
    : "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium";

  if (!href) {
    return (
      <div className="space-y-2">
        <button
          type="button"
          disabled
          className={`${base} cursor-not-allowed bg-white/10 text-zinc-500`}
        >
          Chat on WhatsApp
        </button>
        <p className="text-xs text-zinc-500">
          The WhatsApp link is not set up on this deployment.
        </p>
      </div>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`${base} bg-[#FC8019] text-black transition-colors hover:bg-[#ff933f] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#FC8019]`}
    >
      Chat on WhatsApp
      <ArrowRight className="h-4 w-4" aria-hidden="true" />
    </a>
  );
}

const capabilities = [
  {
    title: "Ask before you buy",
    text: "Price, pack size, stock or delivery fee. Answers come from your Swiggy store.",
    status: "Live",
  },
  {
    title: "Build a basket by chatting",
    text: "“Milk, bread and eggs.” Grocer adds them and shows you the basket.",
    status: "Live",
  },
  {
    title: "Saved addresses",
    text: "See the addresses saved in your Swiggy account.",
    status: "Live",
  },
  {
    title: "Coupons",
    text: "See what is available and what it saves on your basket.",
    status: "Live",
  },
  {
    title: "Order history",
    text: "See past orders from your Swiggy account.",
    status: "Live",
  },
  {
    title: "Track a delivery",
    text: "Follow an active delivery when your Swiggy account has one.",
    status: "In testing",
  },
  {
    title: "Plan a meal",
    text: "Tell Grocer the dish and how many people. It shows the ingredients and packs before adding anything.",
    status: "In testing",
  },
  {
    title: "Reorder",
    text: "Rebuild a basket from a past order or your usual items.",
    status: "In testing",
  },
  {
    title: "Bills and support",
    text: "See an itemised bill, or report a problem with an order.",
    status: "In testing",
  },
  {
    title: "Address changes",
    text: "Add or delete a saved address from the chat.",
    status: "In testing",
  },
  {
    title: "Pay",
    text: "Checkout is locked while the project is being tested. When it opens, you pay on Swiggy’s secure page.",
    status: "In testing",
  },
] as const;

const questions = [
  {
    q: "Is this an official Swiggy app?",
    a: "No. Grocer is an independent project built on Swiggy Instamart’s official tools. It is not a Swiggy product.",
  },
  {
    q: "Where do the prices and stock come from?",
    a: "From Swiggy Instamart, at the store that serves your saved address. Grocer does not make up prices.",
  },
  {
    q: "What happens if something is out of stock?",
    a: "Grocer tells you which item is missing and shows real alternatives when Swiggy has them.",
  },
  {
    q: "Can I cancel an order?",
    a: "Swiggy handles cancellations. Ask Grocer to cancel and it gives you Swiggy Care’s number.",
  },
  {
    q: "How do I delete my data?",
    a: "Send “delete my data” in the chat. Grocer removes your chats, saved location and Swiggy login, and the account is turned into an anonymous record.",
  },
  {
    q: "Why can I not pay yet?",
    a: "Checkout is locked while the project is being tested. Nothing can be ordered or charged until it is opened.",
  },
] as const;

export default function Home() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [showConnect, setShowConnect] = useState(false);
  const [oauthStatus, setOauthStatus] = useState<
    "idle" | "loading" | "connected" | "error"
  >("idle");
  const [oauthMessage, setOauthMessage] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  useEffect(() => {
    if (!process.env.NEXT_PUBLIC_WHATSAPP_NUMBER) {
      console.error(
        "NEXT_PUBLIC_WHATSAPP_NUMBER is not set. The WhatsApp button is disabled.",
      );
    }

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const link = params.get("t");
    const oauthError = params.get("error");

    if (link) {
      setLinkToken(link);
      setShowConnect(true);
    }

    if (oauthError) {
      setShowConnect(true);
      setOauthStatus("error");
      setOauthMessage(
        "Swiggy sign-in was cancelled or failed. Open the link from WhatsApp again.",
      );
    }

    if (code && state) {
      setShowConnect(true);
      setOauthStatus("loading");
      fetch("/api/auth/swiggy/callback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, state }),
      })
        .then(async (res) => {
          const data = await res.json();
          if (!res.ok) {
            throw new Error(
              data.error || data.detail || "Could not finish connecting Swiggy.",
            );
          }
          window.history.replaceState({}, "", window.location.pathname);
          setOauthStatus("connected");
        })
        .catch((err: unknown) => {
          setOauthStatus("error");
          setOauthMessage(
            err instanceof Error
              ? err.message
              : "Could not finish connecting Swiggy. Open the link from WhatsApp again.",
          );
        });
    }
  }, []);

  const handleConnect = async () => {
    if (!linkToken) {
      setOauthStatus("error");
      setOauthMessage(
        "Open the connect link the Grocer bot sent you on WhatsApp.",
      );
      return;
    }

    setIsConnecting(true);
    setOauthMessage(null);
    try {
      const res = await fetch("/api/auth/swiggy/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: linkToken }),
      });
      const data = await res.json();
      if (!res.ok || !data.authorizeUrl) {
        throw new Error(
          data.error || data.detail || "Could not start the Swiggy login.",
        );
      }
      window.location.href = data.authorizeUrl;
    } catch (err: unknown) {
      setOauthStatus("error");
      setOauthMessage(
        err instanceof Error
          ? err.message
          : "Could not start the Swiggy login. Try again from WhatsApp.",
      );
      setIsConnecting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-[#F4F4F5]">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0A0A0B]/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-5 py-3 sm:px-8">
          <a href="#top" className="flex items-center gap-2.5">
            <img
              src="/logo.svg"
              alt=""
              className="h-8 w-8 rounded-lg object-contain"
            />
            <span className="text-base font-semibold tracking-tight text-white">
              Grocer
            </span>
          </a>
          <nav className="hidden items-center gap-6 text-sm text-zinc-400 sm:flex">
            <a className="hover:text-white" href="#what">
              What it does
            </a>
            <a className="hover:text-white" href="#how">
              How it works
            </a>
            <a className="hover:text-white" href="#privacy">
              Privacy
            </a>
            <a className="hover:text-white" href="#questions">
              Questions
            </a>
          </nav>
          <div className="hidden sm:block">
            <WhatsAppButton />
          </div>
        </div>
      </header>

      <main id="top">
        <section className="border-b border-white/10">
          <div className="mx-auto grid max-w-5xl gap-12 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
            <div>
              <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#FC8019]/25 bg-[#FC8019]/10 px-3 py-1 text-xs font-medium text-[#FC8019]">
                <MessageCircle className="h-3.5 w-3.5" aria-hidden="true" />
                Groceries on WhatsApp
              </p>
              <h1 className="max-w-xl text-4xl font-semibold leading-[1.08] tracking-tight text-white sm:text-6xl">
                Your grocery run, inside WhatsApp.
              </h1>
              <p className="mt-6 max-w-xl text-base leading-relaxed text-zinc-400 sm:text-lg">
                Shop Swiggy Instamart by chatting. Ask about prices, build a
                basket, and pay on Swiggy’s secure page. No extra app to open.
              </p>
              <div className="mt-9 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
                <WhatsAppButton large />
                <a
                  href="#how"
                  className="text-sm font-medium text-zinc-400 underline decoration-white/20 underline-offset-4 hover:text-white"
                >
                  See how it works
                </a>
              </div>
              <p className="mt-5 text-xs text-zinc-500">
                WhatsApp: {WHATSAPP_DISPLAY}. Works with your own Swiggy
                account.
              </p>
            </div>

            <figure className="rounded-2xl border border-white/10 bg-[#111114] p-4 shadow-2xl">
              <figcaption className="mb-4 flex items-center justify-between text-xs text-zinc-500">
                <span>Example chat</span>
                <span className="rounded-full border border-white/10 px-2 py-0.5">
                  Grocer
                </span>
              </figcaption>
              <div className="space-y-3 rounded-xl bg-[#0B141A] p-4">
                <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-[#005C4B] px-4 py-2.5 text-sm leading-relaxed text-white">
                  1 litre milk and 6 eggs
                </div>
                <div className="max-w-[90%] rounded-2xl rounded-bl-md bg-[#202C33] px-4 py-2.5 text-sm leading-relaxed text-zinc-100">
                  Added milk and eggs to your basket. You can review the basket
                  before paying.
                </div>
                <div className="max-w-[90%] rounded-xl border border-white/10 bg-[#111B21] px-4 py-3 text-xs text-zinc-400">
                  <p className="font-medium text-zinc-200">Your basket</p>
                  <p className="mt-1">2 items added</p>
                  <p className="mt-2 text-[#FC8019]">View basket</p>
                </div>
              </div>
              <p className="mt-3 text-[11px] leading-relaxed text-zinc-600">
                Example only. Prices and products come from your Swiggy store.
              </p>
            </figure>
          </div>
        </section>

        {showConnect && (
          <section id="connect" className="border-b border-white/10 bg-[#0E0E10]">
            <div className="mx-auto max-w-2xl px-5 py-12 sm:px-8">
              <div className="rounded-2xl border border-[#FC8019]/25 bg-[#FC8019]/5 p-6 sm:p-8">
                <h2 className="text-xl font-semibold text-white">
                  Connect your Swiggy account
                </h2>
                {oauthStatus === "connected" ? (
                  <div className="mt-4 space-y-5">
                    <div className="flex items-start gap-3">
                      <CheckCircle2
                        className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400"
                        aria-hidden="true"
                      />
                      <p className="text-sm leading-relaxed text-zinc-300">
                        Swiggy is connected. Go back to WhatsApp and send your
                        grocery list.
                      </p>
                    </div>
                    <WhatsAppButton />
                  </div>
                ) : (
                  <div className="mt-4 space-y-5">
                    <p className="text-sm leading-relaxed text-zinc-400">
                      The bot sent you here to finish linking Swiggy. This page
                      never asks for your phone number.
                    </p>
                    {oauthMessage && (
                      <p
                        role="alert"
                        className="rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-xs leading-relaxed text-rose-300"
                      >
                        {oauthMessage}
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={handleConnect}
                      disabled={isConnecting || oauthStatus === "loading"}
                      className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#FC8019] px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-[#ff933f] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isConnecting || oauthStatus === "loading"
                        ? "Opening Swiggy…"
                        : "Continue to Swiggy"}
                      <ArrowRight className="h-4 w-4" aria-hidden="true" />
                    </button>
                    <p className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                      <Lock className="h-3 w-3" aria-hidden="true" />
                      Your login is stored encrypted. Grocer never sees your
                      Swiggy password.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        <section id="what" className="border-b border-white/10">
          <div className="mx-auto max-w-5xl px-5 py-16 sm:px-8 sm:py-24">
            <div className="max-w-2xl">
              <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                What you can do in the chat
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-zinc-400 sm:text-base">
                Grocer is a grocery concierge, not a second shopping app. It
                talks to Swiggy Instamart for you and tells you the truth about
                what it can do today.
              </p>
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {capabilities.map((item) => (
                <article
                  key={item.title}
                  className="rounded-2xl border border-white/10 bg-[#111114] p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">
                      {item.title}
                    </h3>
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        item.status === "Live"
                          ? "bg-emerald-500/10 text-emerald-300"
                          : "bg-white/5 text-zinc-400"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                    {item.text}
                  </p>
                </article>
              ))}
            </div>
            <p className="mt-6 text-xs leading-relaxed text-zinc-500">
              “Live” means it is running on the real service. “In testing” means
              it is built but has not been proven on a real phone yet.
            </p>
          </div>
        </section>

        <section id="how" className="border-b border-white/10">
          <div className="mx-auto max-w-5xl px-5 py-16 sm:px-8 sm:py-24">
            <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              How it works
            </h2>
            <div className="mt-10 grid gap-8 sm:grid-cols-3">
              <div>
                <p className="text-xs font-medium text-[#FC8019]">Step 1</p>
                <h3 className="mt-2 text-base font-semibold text-white">
                  Message the bot
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  Send a list, or ask a question. You do not need to learn
                  commands.
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-[#FC8019]">Step 2</p>
                <h3 className="mt-2 text-base font-semibold text-white">
                  Connect Swiggy once
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  When asked, tap the link the bot sends and sign in on Swiggy’s
                  own page.
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-[#FC8019]">Step 3</p>
                <h3 className="mt-2 text-base font-semibold text-white">
                  Shop and pay
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  Review the basket, then pay on Swiggy’s secure page. Checkout
                  is locked while the project is being tested.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-white/10 bg-[#0E0E10]">
          <div className="mx-auto max-w-5xl px-5 py-16 sm:px-8 sm:py-24">
            <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
              <div>
                <p className="inline-flex items-center gap-2 text-xs font-medium text-emerald-300">
                  <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                  Safe by design
                </p>
                <h2 className="mt-4 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                  You stay in control of your money.
                </h2>
                <p className="mt-4 text-sm leading-relaxed text-zinc-400 sm:text-base">
                  Grocer can help you shop, but it cannot spend your money from a
                  text message.
                </p>
              </div>
              <div className="space-y-5">
                <div className="flex gap-4 rounded-2xl border border-white/10 bg-[#111114] p-5">
                  <Lock
                    className="mt-0.5 h-5 w-5 shrink-0 text-[#FC8019]"
                    aria-hidden="true"
                  />
                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      You tap to pay
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                      Typing “yes” or “place the order” never places an order.
                      Only the pay button does.
                    </p>
                  </div>
                </div>
                <div className="flex gap-4 rounded-2xl border border-white/10 bg-[#111114] p-5">
                  <ShoppingBasket
                    className="mt-0.5 h-5 w-5 shrink-0 text-[#FC8019]"
                    aria-hidden="true"
                  />
                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      The basket is checked again
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                      Before payment, Grocer checks the live cart, prices and
                      stock. If anything changed, it stops and tells you.
                    </p>
                  </div>
                </div>
                <div className="flex gap-4 rounded-2xl border border-white/10 bg-[#111114] p-5">
                  <CheckCircle2
                    className="mt-0.5 h-5 w-5 shrink-0 text-[#FC8019]"
                    aria-hidden="true"
                  />
                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      One tap, one order
                    </h3>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                      A double tap or a slow network cannot create a second
                      charge.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="privacy" className="border-b border-white/10">
          <div className="mx-auto max-w-5xl px-5 py-16 sm:px-8 sm:py-24">
            <div className="rounded-2xl border border-white/10 bg-[#111114] p-6 sm:p-10">
              <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                Your data, kept short.
              </h2>
              <div className="mt-6 grid gap-6 sm:grid-cols-3">
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    24 hours
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                    Chats and saved location are cleared after 24 hours of
                    inactivity.
                  </p>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Encrypted login
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                    Your Swiggy login is stored encrypted. Grocer never sees your
                    password.
                  </p>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    Delete on request
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                    Say “delete my data” in the chat. Your messages, location and
                    Swiggy login are removed.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b border-white/10 bg-[#0E0E10]">
          <div className="mx-auto max-w-5xl px-5 py-14 sm:px-8">
            <div className="flex flex-col gap-4 rounded-2xl border border-white/10 bg-[#111114] p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Built on Swiggy Instamart
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-400">
                  Grocer uses Swiggy Instamart’s official tools and your own
                  Swiggy login. It is an independent project, not a Swiggy
                  product. Prices, stock and payment stay on Swiggy’s side.
                </p>
              </div>
              <span className="shrink-0 rounded-full border border-[#FC8019]/25 bg-[#FC8019]/10 px-3 py-1 text-xs font-medium text-[#FC8019]">
                Independent project
              </span>
            </div>
          </div>
        </section>

        <section id="questions" className="border-b border-white/10">
          <div className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-24">
            <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              Questions
            </h2>
            <div className="mt-8 divide-y divide-white/10 border-y border-white/10">
              {questions.map((item) => (
                <details key={item.q} className="group py-4">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium text-zinc-200">
                    {item.q}
                    <span className="text-zinc-500 group-open:hidden" aria-hidden="true">
                      +
                    </span>
                    <span className="hidden text-zinc-500 group-open:inline" aria-hidden="true">
                      −
                    </span>
                  </summary>
                  <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
                    {item.a}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-[#0A0A0B]">
          <div className="mx-auto max-w-3xl px-5 py-20 text-center sm:px-8">
            <h2 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              Start with a message.
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-zinc-400 sm:text-base">
              Open WhatsApp, say hello, and shop your next grocery run in the
              chat.
            </p>
            <div className="mt-8 flex justify-center">
              <WhatsAppButton large />
            </div>
            <p className="mt-5 text-xs text-zinc-500">
              WhatsApp: {WHATSAPP_DISPLAY}
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/10 px-5 py-8 sm:px-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 text-xs text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
          <p>Grocer — an independent grocery concierge for Swiggy Instamart.</p>
          <p>Not a Swiggy product. Payments stay on Swiggy’s secure page.</p>
        </div>
      </footer>
    </div>
  );
}
