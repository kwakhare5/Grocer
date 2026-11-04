export type FeatureMarkName =
  | "chat"
  | "tag"
  | "house"
  | "receipt"
  | "coupon"
  | "pot"
  | "support"
  | "bin";

type FeatureMarkProps = {
  name: FeatureMarkName;
  className?: string;
};

const ink = "currentColor";

export function FeatureMark({ name, className }: FeatureMarkProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 32 32"
      width="100%"
      height="100%"
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke={ink}
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {name === "chat" ? (
        <>
          <path
            d="M5.5 7.5h21a2 2 0 0 1 2 2v10.6a2 2 0 0 1-2 2H15l-5.4 4v-4H5.5a2 2 0 0 1-2-2V9.5a2 2 0 0 1 2-2Z"
            fill="var(--tone)"
          />
          <circle cx="11" cy="15" r="1.25" fill="#fff" stroke="none" />
          <circle cx="16" cy="15" r="1.25" fill="#fff" stroke="none" />
          <circle cx="21" cy="15" r="1.25" fill="#fff" stroke="none" />
        </>
      ) : null}

      {name === "tag" ? (
        <>
          <path
            d="M5 10V5h9l12.5 12.5-9 9L5 14v-4Z"
            fill="var(--tone)"
          />
          <circle cx="10.2" cy="9.8" r="1.5" fill="#fff" stroke="none" />
        </>
      ) : null}

      {name === "house" ? (
        <>
          <path d="M4.5 15 16 5l11.5 10Z" fill="var(--tone)" />
          <path d="M4.5 15 16 5l11.5 10" />
          <path d="M8 13.5V27h16V13.5" fill="#fff" />
          <path d="M14 21h4v6h-4z" fill="var(--tone)" />
        </>
      ) : null}

      {name === "receipt" ? (
        <>
          <path
            d="M9 4.5h14v22l-2.3-1.6-2.3 1.6-2.4-1.6-2.3 1.6-2.4-1.6L9 26.5Z"
            fill="#fff"
          />
          <path d="M12 6.5h8v3h-8Z" fill="var(--tone)" stroke="none" />
          <path d="M12 13.5h8M12 18h8M12 22h5" />
        </>
      ) : null}

      {name === "coupon" ? (
        <>
          <path
            d="M4.5 9.5h23v4a2.5 2.5 0 0 0 0 5v4h-23v-4a2.5 2.5 0 0 0 0-5v-4Z"
            fill="var(--tone)"
          />
          <path d="M13 10v12" stroke="#fff" strokeDasharray="2 2.4" />
          <circle cx="21.8" cy="16" r="2.1" stroke="#fff" />
        </>
      ) : null}

      {name === "pot" ? (
        <>
          <path d="M7 14h18l-1.8 12.5H8.8Z" fill="var(--tone)" />
          <path d="M5 14h22M8 17H5.5M24 17h2.5" />
          <path d="M11.5 9c0-2.2 2-2.2 2-4.4M16.5 9c0-2.2 2-2.2 2-4.4" />
        </>
      ) : null}

      {name === "support" ? (
        <>
          <circle
            cx="16"
            cy="16"
            r="10.5"
            fill="var(--tone)"
            stroke="currentColor"
          />
          <circle cx="16" cy="16" r="5" fill="#fff" stroke="none" />
          <path
            d="M16 5.5v5.5M16 21v5.5M5.5 16H11M21 16h5.5M8.9 8.9l3.7 3.7M19.4 19.4l3.7 3.7M23.1 8.9l-3.7 3.7M12.6 19.4l-3.7 3.7"
            stroke="#fff"
            strokeWidth="2.4"
          />
        </>
      ) : null}

      {name === "bin" ? (
        <>
          <path d="M6.5 9.5h19M12 9.5V6h8v3.5" />
          <path d="M8.5 9.5 10 27h12l1.5-17.5" fill="var(--tone)" />
          <path d="M14 14v8M18 14v8" stroke="#fff" />
        </>
      ) : null}
    </svg>
  );
}

export function LockMark({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width="100%"
      height="100%"
      aria-hidden="true"
      focusable="false"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="5" y="10.5" width="14" height="10.5" rx="2" />
      <path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7" />
      <circle cx="12" cy="15.4" r="1.2" fill="currentColor" stroke="none" />
      <path d="M12 16.6v1.8" />
    </svg>
  );
}
