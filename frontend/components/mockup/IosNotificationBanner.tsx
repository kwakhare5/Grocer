import React from "react";
import imgModeDefault from "./c26d0f4e6f1d97cbbc8bf76776266dd85318da8e.png";
import imgCustomIconDefault from "./9ee404c0ae57001eef8b631f83a9acce5f986f38.png";

export interface IosNotificationBannerProps {
  title?: string;
  message?: string;
  time?: string;
  onClick?: () => void;
}

type CustomIconProps = {
  className?: string;
  mode?: "Default";
};

function CustomIcon({ className }: CustomIconProps) {
  const modeSrc = typeof imgModeDefault === "string" ? imgModeDefault : (imgModeDefault as { src?: string }).src || "";
  const iconSrc = typeof imgCustomIconDefault === "string" ? imgCustomIconDefault : (imgCustomIconDefault as { src?: string }).src || "";

  return (
    <div className={className || "overflow-clip relative size-[66px]"}>
      <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none size-full" src={modeSrc} />
      <div className="-translate-x-1/2 absolute aspect-[256/256] bottom-0 left-1/2 top-0" data-name="Custom-Icon-Default">
        <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none size-full" src={iconSrc} />
      </div>
    </div>
  );
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

function StackedBanner({ bottomOffset, pxPadding }: { bottomOffset: string; pxPadding: string }) {
  return (
    <div className={`absolute ${bottomOffset} content-stretch flex flex-col h-[8px] items-center justify-end left-0 overflow-clip ${pxPadding} right-0 rounded-[24px]`} data-name="Banner">
      <div className="h-[64px] relative shrink-0 w-full" data-name="Clear Glass">
        <FillShadow />
        <GlassEffect />
      </div>
    </div>
  );
}

function TitleAndDescription({ title, message }: { title?: string; message?: string }) {
  return (
    <div className="[word-break:break-word] content-stretch flex flex-[1_0_0] flex-col h-full items-start justify-center min-w-px relative tracking-[-0.23px]" data-name="Title and Description">
      <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-semibold text-[10.5px] leading-[15px] text-white relative shrink-0 w-full truncate">
        {title || "WhatsApp"}
      </p>
      <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[10.5px] leading-[15px] text-white/90 min-w-full relative shrink-0 w-full line-clamp-2">
        {message || "🥛 Amul Milk 1L is down to 15% (runs out tomorrow). Tap to restock →"}
      </p>
    </div>
  );
}

function TimeAndImage({ time }: { time?: string }) {
  return (
    <div className="content-stretch flex flex-col gap-[5.5px] items-end relative shrink-0" data-name="Time and Image">
      <div className="mix-blend-plus-lighter relative shrink-0" data-name="Time">
        <div className="flex flex-row items-center justify-center size-full">
          <div className="content-stretch flex items-center justify-center relative size-full">
            <p className="[word-break:break-word] font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[9.5px] leading-[15px] relative shrink-0 text-[#8e8e93] text-right whitespace-nowrap">
              {time || "now"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Frame({ title, message, time }: { title?: string; message?: string; time?: string }) {
  return (
    <div className="flex flex-[1_0_0] flex-row items-center self-stretch">
      <div className="content-stretch flex flex-[1_0_0] h-full items-start justify-center min-w-px relative gap-2" data-name="Frame">
        <TitleAndDescription title={title} message={message} />
        <TimeAndImage time={time} />
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
      className="relative rounded-[24px] size-full cursor-pointer select-none group antialiased"
      data-name="Notification - Collapsed"
    >
      <div className="flex flex-row items-center justify-center size-full">
        <div className="content-stretch flex gap-[10px] items-center justify-center pb-[27px] pt-[12px] px-[14px] relative size-full">
          <StackedBanner bottomOffset="bottom-[-1.67px]" pxPadding="px-[20px]" />
          <StackedBanner bottomOffset="bottom-[6.33px]" pxPadding="px-[10px]" />
          <div className="absolute inset-[0_0_14.33px_0]" data-name="Clear Glass">
            <FillShadow />
            <GlassEffect />
          </div>
          <CustomIcon className="overflow-clip relative shrink-0 size-[38.333px]" />
          <Frame title={title} message={message} time={time} />
        </div>
      </div>
    </div>
  );
}
