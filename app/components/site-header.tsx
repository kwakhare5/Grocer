import Link from "next/link";
import { NAV } from "../content";
import { LogoMark } from "./logo";
import { MobileMenu } from "./mobile-menu";

type SiteHeaderProps = {
  href: string | null;
};

export function SiteHeader({ href }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="wrap site-header__inner">
        <Link className="brand" href="/" aria-label="Grocer home">
          <LogoMark className="brand__mark" />
          <span className="brand__name">Grocer</span>
        </Link>

        <nav className="site-nav" aria-label="Primary">
          {NAV.map((item) => (
            <Link key={item.href} className="site-nav__link" href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="site-header__actions">
          <Link className="btn btn--primary" href="/#connect">
            Connect Swiggy
          </Link>
        </div>

        <MobileMenu href={href} />
      </div>
    </header>
  );
}
