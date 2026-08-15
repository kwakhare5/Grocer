import React from "react";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

export interface IosNotificationBannerProps {
  title?: string;
  message?: string;
  time?: string;
  onClick?: () => void;
}

function FillShadow() {
  return (
    <div className="absolute inset-0 rounded-[20px] bg-gradient-to-b from-white/30 via-white/15 to-white/10 backdrop-blur-md backdrop-saturate-[160%] border border-white/40 border-t-white/70 border-l-white/60 shadow-[0_8px_32px_rgba(0,0,0,0.25)]">
      <div aria-hidden className="absolute inset-0 pointer-events-none rounded-[20px]">
        <div className="absolute bg-[rgba(255,255,255,0.15)] inset-0 rounded-[20px]" />
      </div>
    </div>
  );
}

function GlassEffect() {
  return (
    <div className="absolute inset-0 pointer-events-none rounded-[20px]">
      <div aria-hidden className="absolute bg-[rgba(0,0,0,0)] inset-0 rounded-[20px]" />
      <div className="absolute inset-0 rounded-[inherit] shadow-[inset_0_1px_1px_0_rgba(255,255,255,0.8)]" />
    </div>
  );
}

function Banner() {
  return (
    <div className="absolute bottom-[-1.67px] flex flex-col h-[8px] items-center justify-end left-0 overflow-hidden px-[20px] right-0 rounded-[22px]">
      <div className="h-[64px] relative shrink-0 w-full">
        <FillShadow />
        <GlassEffect />
      </div>
    </div>
  );
}

function Banner1() {
  return (
    <div className="absolute bottom-[6.33px] flex flex-col h-[8px] items-center justify-end left-0 overflow-hidden px-[10px] right-0 rounded-[22px]">
      <div className="h-[64px] relative shrink-0 w-full">
        <FillShadow />
        <GlassEffect />
      </div>
    </div>
  );
}

export function IosNotificationBanner({
  title = "WhatsApp",
  message = "🥛 Amul Milk 1L is down to 15% (runs out tomorrow). Tap to restock →",
  time = "now",
  onClick
}: IosNotificationBannerProps) {
  return (
    <div
      onClick={onClick}
      className="relative rounded-[22px] w-full cursor-pointer select-none group antialiased"
      style={{ transform: "translateZ(0)", WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale" }}
    >
      <div className="flex flex-row items-center justify-center w-full">
        <div className="flex gap-2 items-center justify-center pb-[20px] pt-[7px] px-3 relative w-full">
          {/* Stacked Collapsed Cards */}
          <Banner />
          <Banner1 />

          {/* Main Frosted Glass Top Card Surface */}
          <div className="absolute inset-x-0 top-0 bottom-[14.33px]">
            <FillShadow />
            <GlassEffect />
          </div>

          {/* App Icon */}
          <div className="relative shrink-0 w-[32px] h-[32px] rounded-[9px] bg-emerald-600 border border-white/20 flex items-center justify-center z-10 shadow-sm">
            <WhatsAppIcon className="h-4 w-4 text-white shrink-0" />
          </div>

          {/* Content Frame */}
          <div className="flex flex-1 flex-row items-center self-stretch z-10 min-w-0">
            <div className="flex flex-1 items-center justify-between min-w-0 relative">
              {/* Title and Description */}
              <div className="flex flex-1 flex-col justify-center min-w-0 gap-0.5">
                <div className="flex items-baseline justify-between w-full min-w-0">
                  <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-semibold text-[10.5px] leading-[15px] text-white tracking-[-0.23px] truncate drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]">
                    {title}
                  </p>
                  <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[9.5px] leading-[15px] text-white/75 tracking-[-0.23px] ml-2 shrink-0 whitespace-nowrap drop-shadow-[0_1px_1px_rgba(0,0,0,0.5)]">
                    {time}
                  </p>
                </div>
                <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[10.5px] leading-[15px] text-white/95 tracking-[-0.23px] line-clamp-2 drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)]">
                  {message}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
