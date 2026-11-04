type LogoMarkProps = {
  className?: string;
};

export function LogoMark({ className }: LogoMarkProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 512 512"
      width="100%"
      height="100%"
      aria-hidden="true"
      focusable="false"
    >
      <g transform="translate(256, 240) rotate(-4.5) scale(1.26)">
        <path
          d="M -50 -45 C -50 -130 50 -130 50 -45"
          fill="none"
          stroke="currentColor"
          strokeWidth="28"
          strokeLinecap="round"
        />
        <path
          d="M -95 -45 L 95 -45 C 115 -45 130 -25 125 0 L 105 145 C 100 168 82 180 58 180 L -58 180 C -82 180 -100 168 -105 145 L -125 0 C -130 -25 -115 -45 -95 -45 Z"
          fill="currentColor"
        />
        <g transform="translate(0, 35)">
          <ellipse cx="-44" cy="0" rx="11" ry="17" fill="#ffffff" />
          <ellipse cx="44" cy="0" rx="11" ry="17" fill="#ffffff" />
          <path
            d="M -15.5 40 Q 0 52 15.5 40"
            fill="none"
            stroke="#ffffff"
            strokeWidth="5.5"
            strokeLinecap="round"
          />
        </g>
      </g>
    </svg>
  );
}

type MascotProps = {
  tone?: string;
  className?: string;
};

export function Mascot({ tone = "var(--pink)", className }: MascotProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 120 120"
      width="100%"
      height="100%"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M 42 40 C 42 16 78 16 78 40"
        fill="none"
        stroke={tone}
        strokeWidth="9"
        strokeLinecap="round"
      />
      <path
        d="M 22 42 L 98 42 C 104 42 108 47 107 53 L 100 98 C 99 105 93 110 86 110 L 34 110 C 27 110 21 105 20 98 L 13 53 C 12 47 16 42 22 42 Z"
        fill={tone}
      />
      <ellipse cx="45" cy="68" rx="5.5" ry="7" fill="#ffffff" />
      <ellipse cx="75" cy="68" rx="5.5" ry="7" fill="#ffffff" />
      <path
        d="M 50 84 Q 60 92 70 84"
        fill="none"
        stroke="#ffffff"
        strokeWidth="5"
        strokeLinecap="round"
      />
    </svg>
  );
}
