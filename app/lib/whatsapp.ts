const MESSAGE = "Hi Grocer, I would like to shop groceries.";

export function getWhatsAppNumber(): string | null {
  const number = (process.env.NEXT_PUBLIC_WHATSAPP_NUMBER || "").replace(/\D/g, "");
  return number || null;
}

export function getWhatsAppHref(): string | null {
  const number = getWhatsAppNumber();
  if (!number) return null;
  return `https://wa.me/${number}?text=${encodeURIComponent(MESSAGE)}`;
}
