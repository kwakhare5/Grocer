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
    <div className="absolute inset-0 rounded-[23px] shadow-[1.25px_0px_0px_-0.75px_#d0d0d0,-1.25px_0px_0px_-0.75px_#d0d0d0,0px_0px_0px_0.5px_#ccc,0px_8px_15px_0px_rgba(0,0,0,0.02)]" data-name="Fill + Shadow">
      <div aria-hidden className="absolute inset-0 pointer-events-none rounded-[23px]">
        <div className="absolute bg-[#101010] inset-0 mix-blend-plus-lighter rounded-[23px]" />
        <div className="absolute bg-[rgba(255,255,255,0.04)] inset-0 mix-blend-luminosity rounded-[23px]" />
      </div>
    </div>
  );
}

function GlassEffect() {
  return (
    <div className="absolute inset-0 pointer-events-none rounded-[23px]" data-name="Glass Effect">
      <div aria-hidden className="absolute bg-[rgba(0,0,0,0)] inset-0 rounded-[23px]" />
      <div className="absolute inset-0 rounded-[inherit] shadow-[inset_0px_40px_10px_-40px_#282828,inset_0px_-40px_10px_-40px_#282828,inset_0px_40px_30px_-40px_#e6e6e6]" />
    </div>
  );
}

function Banner() {
  return (
    <div className="absolute bottom-[-1.67px] content-stretch flex flex-col h-[8px] items-center justify-end left-0 overflow-clip px-[20px] right-0 rounded-[24px]" data-name="Banner">
      <div className="h-[64px] relative shrink-0 w-full" data-name="Clear Glass">
        <FillShadow />
        <GlassEffect />
      </div>
    </div>
  );
}

function FillShadow1() {
  return (
    <div className="absolute inset-0 rounded-[23px] shadow-[1.25px_0px_0px_-0.75px_#d0d0d0,-1.25px_0px_0px_-0.75px_#d0d0d0,0px_0px_0px_0.5px_#ccc,0px_8px_15px_0px_rgba(0,0,0,0.02)]" data-name="Fill + Shadow">
      <div aria-hidden className="absolute inset-0 pointer-events-none rounded-[23px]">
        <div className="absolute bg-[#101010] inset-0 mix-blend-plus-lighter rounded-[23px]" />
        <div className="absolute bg-[rgba(255,255,255,0.04)] inset-0 mix-blend-luminosity rounded-[23px]" />
      </div>
    </div>
  );
}

function GlassEffect1() {
  return (
    <div className="absolute inset-0 pointer-events-none rounded-[23px]" data-name="Glass Effect">
      <div aria-hidden className="absolute bg-[rgba(0,0,0,0)] inset-0 rounded-[23px]" />
      <div className="absolute inset-0 rounded-[inherit] shadow-[inset_0px_40px_10px_-40px_#282828,inset_0px_-40px_10px_-40px_#282828,inset_0px_40px_30px_-40px_#e6e6e6]" />
    </div>
  );
}

function Banner1() {
  return (
    <div className="absolute bottom-[6.33px] content-stretch flex flex-col h-[8px] items-center justify-end left-0 overflow-clip px-[10px] right-0 rounded-[24px]" data-name="Banner">
      <div className="h-[64px] relative shrink-0 w-full" data-name="Clear Glass">
        <FillShadow1 />
        <GlassEffect1 />
      </div>
    </div>
  );
}

function FillShadow2() {
  return (
    <div className="absolute inset-0 rounded-[23px] shadow-[1.25px_0px_0px_-0.75px_#d0d0d0,-1.25px_0px_0px_-0.75px_#d0d0d0,0px_0px_0px_0.5px_#ccc,0px_8px_15px_0px_rgba(0,0,0,0.02)]" data-name="Fill + Shadow">
      <div aria-hidden className="absolute inset-0 pointer-events-none rounded-[23px]">
        <div className="absolute bg-[#101010] inset-0 mix-blend-plus-lighter rounded-[23px]" />
        <div className="absolute bg-[rgba(255,255,255,0.04)] inset-0 mix-blend-luminosity rounded-[23px]" />
      </div>
    </div>
  );
}

function GlassEffect2() {
  return (
    <div className="absolute inset-0 pointer-events-none rounded-[23px]" data-name="Glass Effect">
      <div aria-hidden className="absolute bg-[rgba(0,0,0,0)] inset-0 rounded-[23px]" />
      <div className="absolute inset-0 rounded-[inherit] shadow-[inset_0px_40px_10px_-40px_#282828,inset_0px_-40px_10px_-40px_#282828,inset_0px_40px_30px_-40px_#e6e6e6]" />
    </div>
  );
}

function TitleAndDescription({ title, message }: { title?: string; message?: string }) {
  return (
    <div className="[word-break:break-word] content-stretch flex flex-1 flex-col justify-center min-w-0 gap-0.5" data-name="Title and Description">
      <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-semibold text-[10.5px] leading-[15px] text-white tracking-[-0.23px] truncate">
        {title || "WhatsApp"}
      </p>
      <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[10.5px] leading-[15px] text-white/90 tracking-[-0.23px] line-clamp-2">
        {message || "🥛 Amul Milk 1L is down to 15% (runs out tomorrow). Tap to restock →"}
      </p>
    </div>
  );
}

function TimeAndImage({ time }: { time?: string }) {
  return (
    <div className="mix-blend-plus-lighter relative shrink-0" data-name="Time">
      <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[9.5px] leading-[15px] text-white/65 tracking-[-0.23px] ml-2 shrink-0 whitespace-nowrap">
        {time || "now"}
      </p>
    </div>
  );
}

function Frame({ title, message, time }: { title?: string; message?: string; time?: string }) {
  return (
    <div className="flex flex-1 flex-row items-center self-stretch z-10 min-w-0">
      <div className="flex flex-1 items-center justify-between min-w-0 relative">
        <div className="flex flex-1 flex-col justify-center min-w-0 gap-0.5">
          <div className="flex items-baseline justify-between w-full min-w-0">
            <TitleAndDescription title={title} message={message} />
            <TimeAndImage time={time} />
          </div>
        </div>
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
      data-name="Notification - Collapsed"
    >
      <div className="flex flex-row items-center justify-center w-full">
        <div className="content-stretch flex gap-2 items-center justify-center pb-[20px] pt-[7px] px-3 relative w-full">
          <Banner />
          <Banner1 />
          <div className="absolute inset-[0_0_14.33px_0]" data-name="Clear Glass">
            <FillShadow2 />
            <GlassEffect2 />
          </div>

          {/* Official WhatsApp App Icon */}
          <div className="relative shrink-0 w-[32px] h-[32px] rounded-[9px] bg-emerald-600 border border-white/20 flex items-center justify-center z-10 shadow-sm">
            <WhatsAppIcon className="h-4 w-4 text-white shrink-0" />
          </div>

          <Frame title={title} message={message} time={time} />
        </div>
      </div>
    </div>
  );
}
