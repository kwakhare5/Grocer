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
      {/* Black Bezel Backing Plate - sits behind children under hardware bezel overlay */}
      <div
        className="absolute z-0 bg-black rounded-[44px]"
        style={{
          left: "3.2%",
          top: "1.5%",
          width: "93.6%",
          height: "97.0%",
        }}
      />

      {/* App Screen Content Container - extends 3px UNDER chassis bezel overlay on all 4 sides so z-20 chassis overlays edges seamlessly */}
      {children && (
        <div
          className="absolute z-10 overflow-hidden text-left bg-black rounded-[44px]"
          style={{
            left: "3.2%",
            top: "1.5%",
            width: "93.6%",
            height: "97.0%",
            transform: "translateZ(0)",
            backfaceVisibility: "hidden",
          }}
        >
          {children}
        </div>
      )}

      {/* iPhone 16 Pro Authentic Chassis & Hardware Bezel Overlay Image */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/iphone-16-pro-frame.png"
        alt="iPhone 16 Pro Chassis"
        style={{ imageRendering: "auto" }}
        className="absolute inset-0 w-full h-full pointer-events-none z-20 object-fill select-none"
      />
    </div>
  );
}
