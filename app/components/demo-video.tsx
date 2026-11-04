import type { CSSProperties } from "react";
import { existsSync } from "node:fs";
import path from "node:path";

const d = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;

export function DemoVideo() {
  const hasVideo = existsSync(path.join(process.cwd(), "public", "demo.mp4"));

  return (
    <section className="section" id="demo">
      <div className="wrap">
        <div className="section-head">
          <div>
            <p className="kicker" data-reveal>
              Demo
            </p>
            <h2 className="h2" data-reveal style={d(40)}>
              See it in action.
            </h2>
          </div>
          <p className="lead" data-reveal style={d(80)}>
            {hasVideo
              ? "A short walkthrough from a real chat: send a list, read the basket, stop before payment."
              : "A short walkthrough is on the way: send a list, read the basket, stop before payment."}
          </p>
        </div>

        <figure className="demo-figure" data-reveal style={d(120)}>
          {hasVideo ? (
            <>
              <video
                className="demo-video"
                controls
                playsInline
                preload="metadata"
              >
                <source src="/demo.mp4" type="video/mp4" />
                Your browser cannot play this video.
              </video>
              <figcaption className="demo-caption">
                A real chat. No order is placed.
              </figcaption>
            </>
          ) : (
            <div className="demo-stage">
              <p className="demo-stage__title">The demo is being recorded.</p>
              <p className="demo-stage__body">
                A real chat, from list to basket. No order is placed.
              </p>
            </div>
          )}
        </figure>
      </div>
    </section>
  );
}
