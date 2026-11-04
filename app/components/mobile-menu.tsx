"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { NAV } from "../content";

type MobileMenuProps = {
  href: string | null;
};

export function MobileMenu({ href }: MobileMenuProps) {
  const ref = useRef<HTMLDetailsElement>(null);

  function close() {
    if (ref.current) ref.current.open = false;
  }

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!ref.current?.open) return;
      if (!ref.current.contains(event.target as Node)) close();
    }

    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  return (
    <details
      className="site-menu"
      ref={ref}
      onKeyDown={(event) => {
        if (event.key === "Escape") close();
      }}
    >
      <summary className="site-menu__button">
        <span>Menu</span>
        <span className="site-menu__bars" aria-hidden="true">
          <i />
          <i />
        </span>
      </summary>
      <nav
        className="site-menu__panel"
        aria-label="Mobile"
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) close();
        }}
      >
        {NAV.map((item) => (
          <Link key={item.href} className="site-menu__link" href={item.href}>
            {item.label}
          </Link>
        ))}
        <Link className="site-menu__link" href="/#connect">
          Connect Swiggy
        </Link>
        {href ? (
          <a
            className="site-menu__link"
            href={href}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open chat
          </a>
        ) : null}
      </nav>
    </details>
  );
}
