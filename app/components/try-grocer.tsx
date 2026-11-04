"use client";

import { useEffect, useState } from "react";
import { PROMPTS } from "../content";
import { LogoMark } from "./logo";

export function TryGrocer() {
  const [active, setActive] = useState(0);
  const [typing, setTyping] = useState(false);

  useEffect(() => {
    if (!typing) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const id = window.setTimeout(() => setTyping(false), reduce ? 0 : 420);
    return () => window.clearTimeout(id);
  }, [typing, active]);

  const prompt = PROMPTS[active];

  return (
    <div className="try">
      <div>
        <p className="kicker kicker--blue">Try it</p>
        <h3 className="try__title">Pick a message. See the reply.</h3>
        <p className="try__lead">
          Real replies from Grocer. Your own basket uses your store.
        </p>

        <div className="try__prompts">
          {PROMPTS.map((item, index) => (
            <button
              key={item.id}
              type="button"
              className="try__prompt"
              aria-pressed={index === active}
              onClick={() => {
                if (index === active) return;
                setTyping(true);
                setActive(index);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="try__chat">
        <div className="chat-demo__frame">
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
            <p className="wa-bubble wa-bubble--user" key={`user-${active}`}>
              {prompt.user}
            </p>
            <p className="wa-bubble wa-bubble--bot" aria-live="polite">
              <span
                className="try__reply"
                key={`bot-${typing ? "typing" : active}`}
              >
                {typing ? (
                  <span className="try__typing" aria-label="Grocer is typing">
                    <i />
                    <i />
                    <i />
                  </span>
                ) : (
                  prompt.reply
                )}
              </span>
            </p>
          </div>
        </div>
        <p className="chat-demo__caption">Sample reply.</p>
      </div>
    </div>
  );
}
