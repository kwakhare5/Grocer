import type { HTMLAttributes, ReactNode } from "react";

// Exact iPhone 16 Pro Physical Hardware Specs: 71.5mm (W) x 149.6mm (H), 19.5:9 display
const PHONE_WIDTH = 71.5;
const PHONE_HEIGHT = 149.6;
const SCREEN_X = 2.4;
const SCREEN_Y = 2.4;
const SCREEN_WIDTH = 66.7;
const SCREEN_HEIGHT = 144.8;
const SCREEN_RADIUS = 8.2;

// Calculated percentages for exact subpixel accuracy
const LEFT_PCT = (SCREEN_X / PHONE_WIDTH) * 100;
const TOP_PCT = (SCREEN_Y / PHONE_HEIGHT) * 100;
const WIDTH_PCT = (SCREEN_WIDTH / PHONE_WIDTH) * 100;
const HEIGHT_PCT = (SCREEN_HEIGHT / PHONE_HEIGHT) * 100;

export interface IphoneProps extends HTMLAttributes<HTMLDivElement> {
  src?: string;
  videoSrc?: string;
  children?: ReactNode;
}

export function Iphone({
  src,
  videoSrc,
  children,
  className = "",
  style,
  ...props
}: IphoneProps) {
  const hasVideo = !!videoSrc;
  const hasMedia = hasVideo || !!src || !!children;

  return (
    <div
      className={`relative inline-block w-full align-middle leading-none ${className}`}
      style={{
        aspectRatio: `${PHONE_WIDTH}/${PHONE_HEIGHT}`,
        ...style,
      }}
      {...props}
    >
      {/* iPhone 16 Pro 6.3" Screen Content Container */}
      {children && (
        <div
          className="absolute z-10 overflow-hidden text-left bg-slate-50"
          style={{
            left: `${LEFT_PCT}%`,
            top: `${TOP_PCT}%`,
            width: `${WIDTH_PCT}%`,
            height: `${HEIGHT_PCT}%`,
            borderRadius: `38px`,
          }}
        >
          {children}
        </div>
      )}

      {/* iPhone 16 Pro Hardware Chassis (71.5mm x 149.6mm) */}
      <svg
        viewBox={`0 0 ${PHONE_WIDTH} ${PHONE_HEIGHT}`}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="absolute inset-0 size-full pointer-events-none z-20"
        style={{ transform: "translateZ(0)" }}
      >
        <g mask={hasMedia ? "url(#screenPunch)" : undefined}>
          {/* Outer Grade-5 Titanium Frame */}
          <rect
            x="0.2"
            y="0.2"
            width={PHONE_WIDTH - 0.4}
            height={PHONE_HEIGHT - 0.4}
            rx="9.5"
            className="fill-[#0F172A] stroke-[#334155] stroke-[0.4]"
          />
          {/* Ultra-thin 1.2mm Screen Bezel Trim */}
          <rect
            x="1.0"
            y="1.0"
            width={PHONE_WIDTH - 2.0}
            height={PHONE_HEIGHT - 2.0}
            rx="8.8"
            className="fill-[#1E293B]"
          />
        </g>

        {/* Screen Outline */}
        <rect
          x={SCREEN_X}
          y={SCREEN_Y}
          width={SCREEN_WIDTH}
          height={SCREEN_HEIGHT}
          rx={SCREEN_RADIUS}
          className="fill-none stroke-[#0F172A] stroke-[0.2]"
          mask={hasMedia ? "url(#screenPunch)" : undefined}
        />

        {/* iPhone 16 Pro Dynamic Island (Pill Notch) */}
        <rect
          x="24.2"
          y="4.2"
          width="23.1"
          height="5.4"
          rx="2.7"
          className="fill-[#090D16]"
        />
        {/* Camera Lens Circle */}
        <circle cx="43.8" cy="6.9" r="0.8" className="fill-[#1E293B]" />
        <circle cx="43.8" cy="6.9" r="0.4" className="fill-[#0F172A]" />

        <defs>
          <mask id="screenPunch" maskUnits="userSpaceOnUse">
            <rect
              x="0"
              y="0"
              width={PHONE_WIDTH}
              height={PHONE_HEIGHT}
              fill="white"
            />
            <rect
              x={SCREEN_X}
              y={SCREEN_Y}
              width={SCREEN_WIDTH}
              height={SCREEN_HEIGHT}
              rx={SCREEN_RADIUS}
              ry={SCREEN_RADIUS}
              fill="black"
            />
          </mask>
        </defs>
      </svg>
    </div>
  );
}
