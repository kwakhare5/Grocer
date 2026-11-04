import { ImageResponse } from "next/og";

export const alt = "Grocer — your Swiggy Instamart, on WhatsApp";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const TONES = ["#fb3c98", "#03a2fe", "#00a63e", "#fe9a00", "#f54900"];

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#ffffff",
          padding: "72px",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 60,
              height: 60,
              borderRadius: 14,
              background: "#1E8CFF",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontSize: 32,
              fontWeight: 700,
            }}
          >
            G
          </div>
          <div style={{ fontSize: 38, fontWeight: 700, color: "#0b0b0c" }}>
            Grocer
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              maxWidth: 920,
              color: "#0b0b0c",
              fontSize: 68,
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: -2,
            }}
          >
            Your Swiggy Instamart, on WhatsApp.
          </div>
          <div style={{ color: "#6b6b6b", fontSize: 28 }}>
            Connect once. Send a list. Get a live basket.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {TONES.map((tone) => (
            <div
              key={tone}
              style={{
                width: 18,
                height: 18,
                borderRadius: 4,
                background: tone,
              }}
            />
          ))}
          <div style={{ marginLeft: 12, color: "#6b6b6b", fontSize: 20 }}>
            Independent · Swiggy Instamart tools
          </div>
        </div>
      </div>
    ),
    size,
  );
}
