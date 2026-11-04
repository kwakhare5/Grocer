import Link from "next/link";
import { NAV } from "../content";

export function SiteHeader() {
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

        <Link className="button button--primary site-header__cta" href="/#connect">
          Connect
        </Link>
      </div>
    </header>
  );
}
