import type { CSSProperties } from "react";

const NODES = [
  { id: "chat", label: "You message", tone: "var(--blue)" },
  { id: "store", label: "Swiggy store", tone: "var(--green)" },
  { id: "basket", label: "Basket", tone: "var(--orange)" },
  { id: "bill", label: "Your bill", tone: "var(--pink)" },
] as const;

function RouteIcon({ id }: { id: (typeof NODES)[number]["id"] }) {
  return (
    <svg
      viewBox="0 0 48 48"
      width="100%"
      height="100%"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {id === "chat" ? (
        <>
          <path
            d="M8 12h32a3 3 0 0 1 3 3v15a3 3 0 0 1-3 3H23l-8 6v-6H8a3 3 0 0 1-3-3V15a3 3 0 0 1 3-3Z"
            fill="var(--tone)"
          />
          <path d="M15 22h18M15 27h11" stroke="#fff" />
        </>
      ) : null}

      {id === "store" ? (
        <>
          <path d="M7 20 12 8h24l5 12" fill="var(--tone)" />
          <path d="M7 20h34v22H7Z" fill="#fff" />
          <path d="M12 20v-8M20 20v-8M28 20v-8M36 20v-8M7 20h34" />
          <path d="M18 42V30h12v12" fill="var(--tone)" />
        </>
      ) : null}

      {id === "basket" ? (
        <>
          <path d="M12 20h24l-3 20H15Z" fill="var(--tone)" />
          <path d="M17 20c0-8 3-12 7-12s7 4 7 12" />
          <path d="M17 27v8M24 27v8M31 27v8" stroke="#fff" />
        </>
      ) : null}

      {id === "bill" ? (
        <>
          <path
            d="M13 6h22v36l-3.7-2.7-3.6 2.7-3.7-2.7-3.6 2.7-3.7-2.7L13 42Z"
            fill="#fff"
          />
          <path d="M19 15h10" stroke="var(--tone)" strokeWidth="3" />
          <path d="M19 22h10M19 28h7" />
        </>
      ) : null}
    </svg>
  );
}

export function HowRoute() {
  return (
    <div className="route" data-route aria-label="How Grocer works">
      <span className="route__track" aria-hidden="true" />
      <ol className="route__list">
        {NODES.map((node, index) => (
          <li
            className="route__node"
            key={node.id}
            style={{ "--tone": node.tone, "--i": index } as CSSProperties}
          >
            <span className="route__art" aria-hidden="true">
              <RouteIcon id={node.id} />
            </span>
            <span className="route__label">{node.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
