import Link from "next/link";
import { WhatsAppButton } from "./whatsapp-button";

type SiteFooterProps = {
  href: string | null;
};

export function SiteFooter({ href }: SiteFooterProps) {
  return (
    <footer className="site-footer">
      <div className="wrap">
        <div className="footer-top">
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
          <p className="footer-line">Instamart, in your chats.</p>
          <WhatsAppButton href={href} />
        </div>

        <div className="footer-bottom">
          <nav className="footer-links" aria-label="Footer">
            <Link href="/privacy">Privacy</Link>
            <Link href="/#faq">Questions</Link>
          </nav>
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
