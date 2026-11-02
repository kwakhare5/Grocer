"use client";

import { useEffect, useState } from "react";

type OAuthStatus = "idle" | "loading" | "connected" | "error";

type ConnectCardProps = {
  whatsappHref: string | null;
};

export function ConnectCard({ whatsappHref }: ConnectCardProps) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [showConnect, setShowConnect] = useState(false);
  const [oauthStatus, setOauthStatus] = useState<OAuthStatus>("idle");
  const [oauthMessage, setOauthMessage] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  useEffect(() => {
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
      setOauthMessage("Swiggy sign-in was cancelled or failed.");
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
              data.error || "Could not finish connecting Swiggy.",
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

  async function handleConnect() {
    if (!linkToken) {
      setOauthStatus("error");
      setOauthMessage("The connect link is missing.");
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
          data.error || "Could not start the Swiggy login.",
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
  }

  if (!showConnect) return null;

  return (
    <aside className="connect" aria-label="Swiggy connection">
      <div className="wrap connect__inner">
        <div>
          <p className="connect__title">Connect Swiggy once</p>
          <p className="connect__body">
            Sign in on Swiggy’s page. Grocer reads your live Instamart store and
            builds the basket. It never sees your password.
          </p>
        </div>

        <div className="connect__action">
          {oauthStatus === "idle" ? (
            <button
              type="button"
              className="button"
              onClick={handleConnect}
              disabled={isConnecting}
            >
              {isConnecting ? "Redirecting…" : "Continue to Swiggy"}
            </button>
          ) : null}

          {oauthStatus === "loading" ? (
            <p className="connect__status" role="status" aria-busy="true">
              Connecting to Swiggy…
            </p>
          ) : null}

          {oauthStatus === "connected" ? (
            <div className="connect__result" role="status">
              <p className="connect__success">Swiggy connected.</p>
              <p className="connect__body">
                Head back to WhatsApp and send your list.
              </p>
              {whatsappHref ? (
                <a
                  className="button"
                  href={whatsappHref}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Chat on WhatsApp
                </a>
              ) : (
                <span className="button button--disabled" aria-disabled="true">
                  Chat on WhatsApp
                </span>
              )}
            </div>
          ) : null}

          {oauthStatus === "error" ? (
            <div className="connect__result" role="alert">
              <p className="connect__error">Could not connect.</p>
              <p className="connect__body">
                {oauthMessage || "Something went wrong."}
              </p>
              <p className="connect__body">
                Open the connect link from WhatsApp again.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
