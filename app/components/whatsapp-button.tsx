type WhatsAppButtonProps = {
  href: string | null;
};

export function WhatsAppButton({ href }: WhatsAppButtonProps) {
  if (!href) {
    return (
      <span
        className="button button--disabled"
        aria-disabled="true"
        title="The WhatsApp link is not configured on this deployment."
      >
        Open WhatsApp
      </span>
    );
  }

  return (
    <a className="button" href={href} target="_blank" rel="noopener noreferrer">
      Open WhatsApp
    </a>
  );
}
