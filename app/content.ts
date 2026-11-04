export const NAV = [
  { label: "What it does", href: "/#what" },
  { label: "How it works", href: "/#how" },
  { label: "Connect", href: "/#connect" },
  { label: "Safety", href: "/#safety" },
  { label: "FAQ", href: "/#faq" },
] as const;

export const SAMPLE = {
  count: "6 products",
  itemTotal: "₹343.00",
  couponLabel: "Sample coupon",
  couponAmount: "− ₹40.00",
  handling: "₹9.00",
  delivery: "FREE",
  toPay: "₹312",
  capLabel: "₹312 of ₹1,000",
  capWidth: "31%",
} as const;

export const CHAT = {
  hello: "Hi. What do you need from Instamart?",
  list: "milk, eggs, bread, paneer",
  found: "Found 4 items. Your basket is ₹312 with delivery.",
  ready: "Tap Pay when you are ready.",
  basket: [
    { name: "Milk 500 ml", qty: "×2", price: "₹64" },
    { name: "Eggs (6)", qty: "×1", price: "₹60" },
    { name: "Brown bread", qty: "×1", price: "₹45" },
    { name: "Paneer 200 g", qty: "×1", price: "₹89" },
  ],
  toPay: "₹312",
} as const;

export const FEATURES = [
  {
    name: "Build your basket",
    line: "Say the list. Grocer finds the right pack, checks stock, and adds it.",
    tone: "blue",
    wide: true,
  },
  {
    name: "See live prices",
    line: "Items, fees and coupons before you pay. Read from Swiggy at that moment.",
    tone: "purple",
  },
  {
    name: "Plan a meal",
    line: "A recipe turns into a priced list you can add in one tap.",
    tone: "green",
  },
  {
    name: "Switch addresses",
    line: "List, add, or remove a saved Swiggy address, then pick the one you mean.",
    tone: "yellow",
  },
  {
    name: "Follow the order",
    line: "See where it is and when it lands, in the same chat.",
    tone: "brown",
  },
  {
    name: "Get help",
    line: "Bills, missing items, refunds, or “delete my data”.",
    tone: "muted",
  },
] as const;

export const HOW = [
  {
    title: "Connect once",
    body: "Enter your number here. Send the code on WhatsApp, then sign in on Swiggy’s page.",
    tone: "blue",
  },
  {
    title: "Send your list",
    body: "Type it the way you would text a friend. Grocer builds a real Instamart basket.",
    tone: "purple",
  },
  {
    title: "Tap Pay",
    body: "Check every item and fee. Only the Pay button can place the order.",
    tone: "green",
  },
] as const;

export const STEPS = [
  {
    title: "You tap Pay.",
    body: "A text cannot order. Only the Pay button can.",
  },
  {
    title: "Grocer checks again.",
    body: "Live prices, live stock. If something moved or sold out, you see it before paying.",
  },
  {
    title: "It runs once.",
    body: "One approval, one order. A double tap bounces off.",
  },
] as const;

export const FACTS = [
  {
    value: "20",
    label: "Swiggy tools",
    note: "Catalog, cart, addresses, orders, payments and support.",
    tone: "blue",
  },
  {
    value: "4",
    label: "safety levels",
    note: "Every message is read, basket, account or money.",
    tone: "purple",
  },
  {
    value: "1",
    label: "AI model",
    note: "One brain for language. Python holds the rules.",
    tone: "green",
  },
  {
    value: "₹1,000",
    label: "safety cap",
    note: "Go over it and Grocer waits for your say-so.",
    tone: "yellow",
  },
] as const;

export const FAQS = [
  {
    q: "Is Grocer an official Swiggy app?",
    a: "No. Grocer is an independent app built on Swiggy’s official Instamart tools. Your order and payment stay with Swiggy.",
  },
  {
    q: "How do I connect my Swiggy account?",
    a: "Enter your WhatsApp number on this page. We open WhatsApp with a short code. Send it from that number, and the bot replies with a private Swiggy sign-in link. Grocer never asks for your password or UPI PIN.",
  },
  {
    q: "Can I pay yet?",
    a: "Not yet. The chat, live prices and basket work today. Payments open next.",
  },
  {
    q: "Does Grocer charge me?",
    a: "No fee and no markup. You pay Swiggy’s prices and fees.",
  },
  {
    q: "What if something is out of stock?",
    a: "Grocer tells you and shows a real alternative if there is one. It never swaps anything without asking.",
  },
  {
    q: "Where does my data go?",
    a: "Address and basket copies are deleted after 24 hours. The number you type on this page is not stored. Your Swiggy login is protected, and “delete my data” removes what Grocer stores.",
  },
] as const;
