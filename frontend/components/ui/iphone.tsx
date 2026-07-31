import type { HTMLAttributes, ReactNode } from "react";

export interface IphoneProps extends HTMLAttributes<HTMLDivElement> {
  src?: string;
  videoSrc?: string;
  children?: ReactNode;
}

export function Iphone({
  children,
  className = "",
  style,
  ...props
}: IphoneProps) {
  return (
    <div
      className={`relative inline-block w-full align-middle leading-none overflow-hidden bg-transparent ${className}`}
      style={{
        aspectRatio: "1800/3680",
        ...style,
      }}
      {...props}
    >
      {/* Black Bezel Backing Plate - sits under black titanium bezel overlay */}
      <div
        className="absolute z-0 bg-black rounded-[44px]"
        style={{
          left: "5.0%",
          top: "2.3%",
          width: "90.0%",
          height: "95.4%",
        }}
      />

      {/* App Screen Content Container positioned seamlessly inside transparent chassis cutout */}
      {children && (
        <div
          className="absolute z-10 overflow-hidden text-left bg-[#F6F7F8]"
          style={{
            left: "5.0%",
            top: "2.3%",
            width: "90.0%",
            height: "95.4%",
            borderRadius: "44px",
          }}
        >
          {children}
        </div>
      )}

      {/* iPhone 16 Pro Authentic Chassis & Hardware Bezel Overlay Image */}
      {/* Includes status bar (9:41, Dynamic Island, Cellular signal, WiFi, Battery) */}
      <img
        src="/Group 1.png"
        alt="iPhone 16 Pro Chassis"
        className="absolute inset-0 size-full pointer-events-none z-20 object-contain select-none"
      />
    </div>
  );
}

