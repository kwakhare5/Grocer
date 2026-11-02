import Link from "next/link";
import { NAV } from "../content";
import { WhatsAppButton } from "./whatsapp-button";

type SiteHeaderProps = {
  href: string | null;
};

export function SiteHeader({ href }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="wrap site-header__inner">
        <Link className="brand" href="/" aria-label="Grocer home">
          <img
            className="brand__mark"
            src="/logo-mark.svg"
            alt=""
            width={24}
            height={24}
          />
          <span className="brand__name">Grocer</span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          {NAV.map((item) => (
            <Link key={item.href} className="site-nav__link" href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>

        <WhatsAppButton href={href} />
      </div>
    </header>
  );
}
