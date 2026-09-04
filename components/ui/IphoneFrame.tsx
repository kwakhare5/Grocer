import type { HTMLAttributes, ReactNode } from "react";

export interface IphoneFrameProps extends HTMLAttributes<HTMLDivElement> {
  src?: string;
  videoSrc?: string;
  children?: ReactNode;
}

export function IphoneFrame({
  children,
  className = "",
  style,
  ...props
}: IphoneFrameProps) {
  return (
    <div
      className={`relative inline-block w-full align-middle leading-none overflow-hidden bg-transparent antialiased ${className}`}
      style={{
        aspectRatio: "1800/3680",
        transform: "translateZ(0)",
        backfaceVisibility: "hidden",
        WebkitFontSmoothing: "antialiased",
        MozOsxFontSmoothing: "grayscale",
        textRendering: "optimizeLegibility",
        ...style,
      }}
      {...props}
    >
      {/* Black Bezel Backing Plate */}
      <div
        className="absolute z-0 bg-black rounded-[24px]"
        style={{
          left: "5.39%",
          top: "2.53%",
          width: "89.17%",
          height: "94.92%",
        }}
      />

      {/* App Screen Content Container */}
      {children && (
        <div
          className="absolute z-10 overflow-hidden text-left bg-black rounded-[24px]"
          style={{
            left: "5.39%",
            top: "2.53%",
            width: "89.17%",
            height: "94.92%",
            transform: "translateZ(0)",
            backfaceVisibility: "hidden",
          }}
        >
          {children}
        </div>
      )}

      {/* iPhone 17 Pro Authentic Chassis Overlay Image */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/iPhone 17 Pro frame.png"
        alt="iPhone 17 Pro Chassis"
        style={{ imageRendering: "auto" }}
        className="absolute inset-0 w-full h-full pointer-events-none z-20 object-fill select-none"
      />
    </div>
  );
}
