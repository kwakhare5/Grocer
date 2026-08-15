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
    <div className="absolute inset-0 rounded-[23px] bg-[rgba(255,255,255,0.18)] backdrop-blur-xl backdrop-saturate-[180%] border border-white/40 shadow-[0_8px_24px_rgba(0,0,0,0.2)]">
      <div aria-hidden className="absolute inset-0 pointer-events-none rounded-[23px]">
        <div className="absolute bg-[rgba(255,255,255,0.12)] inset-0 rounded-[23px]" />
      </div>
    </div>
  );
}

function GlassEffect() {
  return (
    <div className="absolute inset-0 pointer-events-none rounded-[23px]">
      <div aria-hidden className="absolute bg-[rgba(0,0,0,0)] inset-0 rounded-[23px]" />
      <div className="absolute inset-0 rounded-[inherit] shadow-[inset_0_1px_1px_0_rgba(255,255,255,0.75)]" />
    </div>
  );
}

function Banner() {
  return (
    <div className="absolute bottom-[-1.67px] content-stretch flex flex-col h-[8px] items-center justify-end left-0 overflow-clip px-[20px] right-0 rounded-[24px]">
      <div className="h-[64px] relative shrink-0 w-full">
        <FillShadow />
        <GlassEffect />
      </div>
    </div>
  );
}

function Banner1() {
  return (
    <div className="absolute bottom-[6.33px] content-stretch flex flex-col h-[8px] items-center justify-end left-0 overflow-clip px-[10px] right-0 rounded-[24px]">
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
      className="relative rounded-[24px] w-full cursor-pointer select-none group antialiased"
      style={{ transform: "translateZ(0)", WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale" }}
    >
      <div className="flex flex-row items-center justify-center w-full">
        <div className="content-stretch flex gap-2 items-center justify-center pb-[20px] pt-[7px] px-3 relative w-full">
          <Banner />
          <Banner1 />
          <div className="absolute inset-[0_0_14.33px_0]">
            <FillShadow />
            <GlassEffect />
          </div>

          {/* App Icon */}
          <div className="relative shrink-0 w-[32px] h-[32px] rounded-[9px] bg-emerald-600 border border-white/20 flex items-center justify-center z-10 shadow-sm">
            <WhatsAppIcon className="h-4 w-4 text-white shrink-0" />
          </div>

          {/* Content Frame */}
          <div className="flex flex-1 flex-row items-center self-stretch z-10 min-w-0">
            <div className="content-stretch flex flex-1 h-full items-start justify-between min-w-0 relative">
              <div className="[word-break:break-word] content-stretch flex flex-1 flex-col justify-center min-w-0 relative gap-0.5">
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
