import Link from "next/link";
import { LogoMark } from "./logo";

type SiteFooterProps = {
  href: string | null;
};

export function SiteFooter({ href }: SiteFooterProps) {
  return (
    <footer className="site-footer">
      <div className="wrap">
        <div className="footer-grid">
          <div className="footer-brand">
            <Link className="brand" href="/" aria-label="Grocer home">
              <LogoMark className="brand__mark" />
              <span className="brand__name">Grocer</span>
            </Link>
            <p className="footer-line">Instamart, in your chats.</p>
          </div>

          <nav className="footer-col" aria-label="Product">
            <p className="footer-col__title">Product</p>
            <Link href="/#what">Features</Link>
            <Link href="/#how">How it works</Link>
            <Link href="/#demo">Demo</Link>
            <Link href="/#connect">Connect</Link>
            <Link href="/#safety">Safety</Link>
          </nav>

          <nav className="footer-col" aria-label="Project">
            <p className="footer-col__title">Project</p>
            <Link href="/privacy">Privacy</Link>
            <Link href="/#faq">FAQ</Link>
            <a
              href="https://github.com/kwakhare5/Grocer/issues"
              target="_blank"
              rel="noopener noreferrer"
            >
              Report an issue
            </a>
          </nav>

          <nav className="footer-col" aria-label="Built on">
            <p className="footer-col__title">Built on</p>
            <span>Swiggy Instamart tools</span>
            <span>WhatsApp Cloud API</span>
            <span>Groq</span>
            <span>PostgreSQL</span>
          </nav>

          <div className="footer-col">
            <p className="footer-col__title">Contact</p>
            {href ? (
              <a href={href} target="_blank" rel="noopener noreferrer">
                Open chat
              </a>
            ) : (
              <span>WhatsApp link not set</span>
            )}
          </div>
        </div>

        <div className="footer-bottom">
          <p className="footer-legal">
            Independent app, built on Swiggy’s official Instamart tools. Not
            affiliated with Swiggy. Swiggy and Instamart are trademarks of
            Swiggy.
          </p>
          <p className="footer-copy">© {new Date().getFullYear()} Grocer</p>
        </div>
      </div>
    </footer>
  );
}
