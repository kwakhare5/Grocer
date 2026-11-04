"use client";

import { useState } from "react";

type ConnectFormProps = {
  whatsappNumber: string | null;
};

export function ConnectForm({ whatsappNumber }: ConnectFormProps) {
  const [phone, setPhone] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!whatsappNumber) {
      setError("Connecting is not configured on this deployment yet.");
      return;
    }

    const digits = phone.replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "");
    if (!/^[6-9]\d{9}$/.test(digits)) {
      setError("Enter a 10-digit Indian mobile number.");
      return;
    }

    setBusy(true);
    try {
      const res = await fetch("/api/auth/whatsapp/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: digits }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || typeof data.token !== "string") {
        throw new Error(data.error || "Could not create a connect code. Try again.");
      }
      setToken(data.token);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not create a connect code. Try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  const waHref =
    token && whatsappNumber
      ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(`connect ${token}`)}`
      : null;

  if (!whatsappNumber) {
    return (
      <div className="connect-form">
        <p className="connect-form__step">Connect</p>
        <h3 className="connect-form__title">Connecting is off.</h3>
        <p className="connect-form__body">
          This deployment has no WhatsApp number set, so the form cannot
          create a code.
        </p>
      </div>
    );
  }

  if (waHref) {
    return (
      <div className="connect-form" role="status">
        <p className="connect-form__step">Code ready</p>
        <h3 className="connect-form__title">Send it on WhatsApp.</h3>
        <p className="connect-form__body">
          Tap the button below, then tap Send on the message we prepared. The
          bot replies with your Swiggy sign-in button.
        </p>
        <a
          className="btn btn--primary btn--lg connect-form__submit"
          href={waHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open WhatsApp
        </a>
        <p className="connect-form__note">
          The code works for 10 minutes. Send it from the same number you
          entered.
        </p>
        <button
          className="connect-form__reset"
          type="button"
          onClick={() => {
            setToken(null);
            setPhone("");
          }}
        >
          Use a different number
        </button>
      </div>
    );
  }

  return (
    <form className="connect-form" onSubmit={handleSubmit} noValidate>
      <h3 className="connect-form__title">Enter your number.</h3>
      <p className="connect-form__body">
        We send a one-time Swiggy sign-in link to this WhatsApp number. We do
        not store it.
      </p>

      <label className="connect-form__label" htmlFor="connect-phone">
        WhatsApp number
      </label>
      <div className="connect-form__field">
        <span className="connect-form__prefix" aria-hidden="true">
          +91
        </span>
        <input
          id="connect-phone"
          name="phone"
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          maxLength={14}
          placeholder="98765 43210"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          aria-describedby={error ? "connect-error" : "connect-note"}
          aria-invalid={error ? true : undefined}
          disabled={busy}
        />
      </div>

      {error ? (
        <p className="connect-form__error" id="connect-error" role="alert">
          {error}
        </p>
      ) : (
        <p className="connect-form__note" id="connect-note">
          Indian numbers only.
        </p>
      )}

      <button
        className="btn btn--primary btn--lg connect-form__submit"
        type="submit"
        disabled={busy}
      >
        {busy ? "Creating your code…" : "Continue"}
      </button>
    </form>
  );
}
