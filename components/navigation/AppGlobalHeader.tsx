"use client";

import React from "react";
import { GrocerLogo } from "../ui/GrocerLogo";

const whatsappNumber = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER;
const whatsappUrl = whatsappNumber
  ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent("Hi Grocer!")}`
  : null;

export function AppGlobalHeader() {
  return (
    <header className="sticky top-0 z-40 w-full bg-white/95 backdrop-blur-md border-b border-zinc-200">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand identity - Clickable to top */}
        <a href="#" className="flex items-center gap-3 group">
          <GrocerLogo size="sm" iconOnly />
          <div className="flex flex-col">
            <span className="font-bold text-zinc-950 tracking-tight text-base font-sans leading-tight group-hover:text-emerald-700 transition-colors">
              Grocer
            </span>
            <span className="text-xs text-zinc-500 font-sans">
              Grocery replenishment on WhatsApp
            </span>
          </div>
        </a>

        {/* Center Navigation Links */}
        <nav className="hidden md:flex items-center gap-6 text-xs font-sans font-medium text-zinc-600">
          <a
            href="#how-it-works"
            className="hover:text-zinc-950 transition-colors"
          >
            How It Works
          </a>
          <a
            href="#features"
            className="hover:text-zinc-950 transition-colors"
          >
            Features
          </a>
          <a
            href="#demo"
            className="hover:text-zinc-950 transition-colors"
          >
            WhatsApp Demo
          </a>
          <a
            href="#safety"
            className="hover:text-zinc-950 transition-colors"
          >
            Safety
          </a>
        </nav>

        {/* Action */}
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/kwakhare5/Grocer"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700 text-xs font-sans font-medium transition-colors shadow-xs"
          >
            <svg
              className="w-4 h-4 text-zinc-800"
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
              />
            </svg>
            <span className="hidden sm:inline">GitHub</span>
          </a>

          {whatsappUrl && (
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[#25D366] hover:bg-[#1ebd59] text-white text-xs font-sans font-semibold transition-colors shadow-xs"
            >
              <svg
                className="w-4 h-4"
                viewBox="0 0 256 258"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <defs>
                  <linearGradient id="navWhatsappGrad" x1="50%" x2="50%" y1="100%" y2="0%">
                    <stop offset="0%" stopColor="#1faf38" />
                    <stop offset="100%" stopColor="#60d669" />
                  </linearGradient>
                  <linearGradient id="navWhatsappBg" x1="50%" x2="50%" y1="100%" y2="0%">
                    <stop offset="0%" stopColor="#f9f9f9" />
                    <stop offset="100%" stopColor="#fff" />
                  </linearGradient>
                </defs>
                <path
                  fill="url(#navWhatsappGrad)"
                  d="M5.463 127.456c-.006 21.677 5.658 42.843 16.428 61.499L4.433 252.697l65.232-17.104a123 123 0 0 0 58.8 14.97h.054c67.815 0 123.018-55.183 123.047-123.01c.013-32.867-12.775-63.773-36.009-87.025c-23.23-23.25-54.125-36.061-87.043-36.076c-67.823 0-123.022 55.18-123.05 123.004"
                />
                <path
                  fill="url(#navWhatsappBg)"
                  d="M1.07 127.416c-.007 22.457 5.86 44.38 17.014 63.704L0 257.147l67.571-17.717c18.618 10.151 39.58 15.503 60.91 15.511h.055c70.248 0 127.434-57.168 127.464-127.423c.012-34.048-13.236-66.065-37.3-90.15C194.633 13.286 162.633.014 128.536 0C58.276 0 1.099 57.16 1.071 127.416m40.24 60.376l-2.523-4.005c-10.606-16.864-16.204-36.352-16.196-56.363C22.614 69.029 70.138 21.52 128.576 21.52c28.3.012 54.896 11.044 74.9 31.06c20.003 20.018 31.01 46.628 31.003 74.93c-.026 58.395-47.551 105.91-105.943 105.91h-.042c-19.013-.01-37.66-5.116-53.922-14.765l-3.87-2.295l-40.098 10.513z"
                />
                <path
                  fill="#fff"
                  d="M96.678 74.148c-2.386-5.303-4.897-5.41-7.166-5.503c-1.858-.08-3.982-.074-6.104-.074c-2.124 0-5.575.799-8.492 3.984c-2.92 3.188-11.148 10.892-11.148 26.561s11.413 30.813 13.004 32.94c1.593 2.123 22.033 35.307 54.405 48.073c26.904 10.609 32.379 8.499 38.218 7.967c5.84-.53 18.844-7.702 21.497-15.139c2.655-7.436 2.655-13.81 1.859-15.142c-.796-1.327-2.92-2.124-6.105-3.716s-18.844-9.298-21.763-10.361c-2.92-1.062-5.043-1.592-7.167 1.597c-2.124 3.184-8.223 10.356-10.082 12.48c-1.857 2.129-3.716 2.394-6.9.801c-3.187-1.598-13.444-4.957-25.613-15.806c-9.468-8.442-15.86-18.867-17.718-22.056c-1.858-3.184-.199-4.91 1.398-6.497c1.431-1.427 3.186-3.719 4.78-5.578c1.588-1.86 2.118-3.187 3.18-5.311c1.063-2.126.531-3.986-.264-5.579c-.798-1.593-6.987-17.343-9.819-23.64"
                />
              </svg>
              <span>Open WhatsApp</span>
            </a>
          )}
        </div>
      </div>
    </header>
  );
}
