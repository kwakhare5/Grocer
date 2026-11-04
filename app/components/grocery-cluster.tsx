export function GroceryCluster() {
  return (
    <div className="grocery-cluster" aria-hidden="true">
      <svg
        viewBox="0 0 240 190"
        width="100%"
        height="100%"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M96 64c0-26 48-26 48 0" />
        <path
          d="M70 63h100l-8 105c-.5 7-6 11-13 11H91c-7 0-12.5-4-13-11Z"
          fill="#ffffff"
        />
        <path d="M70 63h100M84 88h72" />

        <g transform="rotate(-5 121 86)">
          <path
            d="M104 42h34v54l-4.2-3-4.3 3-4.2-3-4.3 3-4.2-3-4.3 3L108 93l-4-3Z"
            fill="#ffffff"
          />
          <path d="M111 53h20M111 60h20M111 67h13" strokeWidth="1.4" />
          <rect
            x="111"
            y="74"
            width="17"
            height="5"
            rx="1"
            fill="var(--red-bright)"
            stroke="none"
          />
        </g>

        <g>
          <path d="M30 88 49 64l19 24v66H30Z" fill="#ffffff" />
          <path d="M30 88h38M49 64v24" />
          <rect
            x="36"
            y="108"
            width="26"
            height="27"
            rx="2"
            fill="var(--blue)"
            stroke="none"
          />
          <path
            d="M41 120c4-5 8 5 12 0"
            stroke="#ffffff"
            strokeWidth="1.8"
          />
        </g>

        <g>
          <path
            d="M78 153c-9-13-5-31 12-35 19-4 33 7 34 23 1 12-5 20-15 20H89c-4 0-8-3-11-8Z"
            fill="var(--orange)"
          />
          <path d="M97 123l8 11M110 121l8 11" stroke="#ffffff" strokeWidth="2" />
        </g>

        <g>
          <path d="M158 139h64l-7 26h-50Z" fill="var(--pink)" />
          <path d="M163 133c0-5 5-9 10-9s10 4 10 9v10h-20Z" fill="#ffffff" />
          <path d="M185 133c0-5 5-9 10-9s10 4 10 9v10h-20Z" fill="#ffffff" />
          <path d="M170 133c0-5 5-9 10-9s10 4 10 9" fill="none" />
          <path d="M192 133c0-5 5-9 10-9s10 4 10 9" fill="none" />
          <path d="M165 148h50" strokeWidth="1.4" />
        </g>

        <g fill="var(--green)" stroke="var(--green)" strokeWidth="1.4">
          <path d="M196 101c8-14 21-17 30-9-6 12-19 17-30 9Z" />
          <path d="M199 103c10-9 20-13 28-14" fill="none" />
          <path d="M206 123c-4-10 0-17 10-20 3 9-1 16-10 20Z" />
          <path d="M211 123c4-8 11-11 19-9-3 8-10 12-19 9Z" />
        </g>
      </svg>
    </div>
  );
}
