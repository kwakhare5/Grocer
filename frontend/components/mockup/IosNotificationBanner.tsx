import React from "react";
import { WhatsAppIcon } from "../ui/WhatsAppIcon";

export interface IosNotificationBannerProps {
  title?: string;
  message?: string;
  time?: string;
  onClick?: () => void;
}

/* -------------------------------------------------------------------------- */
/* 1. GLASS BACKDROP SURFACES (INDEPENDENT)                                  */
/* -------------------------------------------------------------------------- */

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

function ClearGlassSurface({ className = "h-[64px]" }: { className?: string }) {
  return (
    <div className={`relative shrink-0 w-full ${className}`} data-name="Clear Glass">
      <FillShadow />
      <GlassEffect />
    </div>
  );
}

function StackedBanner({ bottomOffset, pxPadding }: { bottomOffset: string; pxPadding: string }) {
  return (
    <div className={`absolute ${bottomOffset} content-stretch flex flex-col h-[8px] items-center justify-end left-0 overflow-clip ${pxPadding} right-0 rounded-[24px]`} data-name="Banner">
      <ClearGlassSurface className="h-[64px]" />
    </div>
  );
}

function NotificationGlassBackground() {
  return (
    <div className="absolute inset-0 pointer-events-none" data-name="Glass Background Stack">
      <StackedBanner bottomOffset="bottom-[-1.67px]" pxPadding="px-[20px]" />
      <StackedBanner bottomOffset="bottom-[6.33px]" pxPadding="px-[10px]" />
      <div className="absolute inset-[0_0_14.33px_0]" data-name="Clear Glass">
        <FillShadow />
        <GlassEffect />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 2. FOREGROUND CONTENT & ICON COMPONENTS (INDEPENDENT)                      */
/* -------------------------------------------------------------------------- */

function WhatsAppIconBadge() {
  return (
    <div className="relative shrink-0 w-[32px] h-[32px] rounded-[9px] bg-emerald-600 border border-white/20 flex items-center justify-center z-10 shadow-sm">
      <WhatsAppIcon className="h-4 w-4 text-white shrink-0" />
    </div>
  );
}

function NotificationHeader({ title, time }: { title?: string; time?: string }) {
  return (
    <div className="flex items-baseline justify-between w-full min-w-0">
      <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-semibold text-[10.5px] leading-[15px] text-white tracking-[-0.23px] truncate">
        {title || "WhatsApp"}
      </p>
      <div className="mix-blend-plus-lighter relative shrink-0" data-name="Time">
        <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[9.5px] leading-[15px] text-white/65 tracking-[-0.23px] ml-2 shrink-0 whitespace-nowrap">
          {time || "now"}
        </p>
      </div>
    </div>
  );
}

function NotificationMessage({ message }: { message?: string }) {
  return (
    <p className="font-['SF_Pro_Text',-apple-system,sans-serif] font-normal text-[10.5px] leading-[15px] text-white/90 min-w-full relative shrink-0 w-full line-clamp-2">
      {message || "🥛 Amul Milk 1L is down to 15% (runs out tomorrow). Tap to restock →"}
    </p>
  );
}

function NotificationTextFrame({ title, message, time }: { title?: string; message?: string; time?: string }) {
  return (
    <div className="flex flex-1 flex-row items-center self-stretch z-10 min-w-0" data-name="Text Frame">
      <div className="flex flex-1 flex-col justify-center min-w-0 gap-0.5">
        <NotificationHeader title={title} time={time} />
        <NotificationMessage message={message} />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* 3. MAIN NOTIFICATION BANNER CONTAINER                                      */
/* -------------------------------------------------------------------------- */

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
      <div className="flex flex-row items-center justify-center size-full relative">
        {/* Isolated Glass Background Layer Stack */}
        <NotificationGlassBackground />

        {/* Isolated Foreground Content Container */}
        <div className="content-stretch flex gap-[9px] items-center justify-center pb-[20px] pt-[8px] px-[13px] relative size-full z-10" data-name="Content Container">
          <WhatsAppIconBadge />
          <NotificationTextFrame title={title} message={message} time={time} />
        </div>
      </div>
    </div>
  );
}
