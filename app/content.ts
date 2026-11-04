export const NAV = [
  { label: "Features", href: "/#what" },
  { label: "How it works", href: "/#how" },
  { label: "Demo", href: "/#demo" },
  { label: "Safety", href: "/#safety" },
  { label: "FAQ", href: "/#faq" },
] as const;

export const HERO = {
  badge: "Independent · Swiggy Instamart tools",
  title: "Your Swiggy Instamart, on WhatsApp.",
  support:
    "Connect your Swiggy account, send a list, and get a live basket with real prices.",
  micro: ["No new app", "Live store prices", "Payments open next"],
} as const;

export const CONNECT_STEPS = [
  "Enter your WhatsApp number.",
  "Send the prepared code from that number.",
  "Sign in on Swiggy’s page.",
] as const;

export const LIVE_RECEIPT = {
  user: "milk, 6 eggs and brown bread",
  items: [
    {
      name: "Amul Slim n Trim UHT Skimmed Milk (1 ltr)",
      qty: 1,
      price: "₹85",
    },
    { name: "Yolkers Classic Eggs (6 Pieces)", qty: 1, price: "₹51" },
    { name: "Bakers World Brown Bread (400 g)", qty: 1, price: "₹41" },
  ],
  itemTotal: "₹177.00",
  handling: "₹10.01",
  delivery: "FREE",
  toPay: "₹187",
  buttons: ["Pay ₹187", "Clear basket"],
} as const;

export const FEATURES = [
  {
    title: "Say it in plain words",
    body: "Add, change, remove or clear items in one message. No catalogue to click through.",
    tone: "blue",
    mark: "chat",
  },
  {
    title: "See the real price",
    body: "Live prices, pack sizes, stock and fees from your Instamart store.",
    tone: "green",
    mark: "tag",
  },
  {
    title: "Use your saved address",
    body: "See your saved addresses and switch stores. Grocer rebuilds the basket for the new store.",
    tone: "orange",
    mark: "house",
  },
  {
    title: "Know what you ordered",
    body: "Order history, itemised bills and delivery status. If there is no order, Grocer says so.",
    tone: "pink",
    mark: "receipt",
  },
  {
    title: "Let coupons be checked",
    body: "Valid coupons are checked on every basket change, and the savings show on the receipt.",
    tone: "red",
    mark: "coupon",
  },
  {
    title: "Plan a meal",
    body: "Name a dish. Grocer prices the ingredients and builds the basket.",
    tone: "blue",
    mark: "pot",
  },
  {
    title: "Report a problem",
    body: "Send an order problem to Swiggy support from the chat.",
    tone: "green",
    mark: "support",
  },
  {
    title: "Delete your data",
    body: "Remove the Swiggy link and the chat copy Grocer stores.",
    tone: "orange",
    mark: "bin",
  },
] as const;

export const PROMPTS = [
  {
    id: "basket",
    label: "Build a basket",
    user: "add 6 eggs and brown bread",
    reply: "✅ Added to your basket · 3 items · To Pay ₹187",
  },
  {
    id: "check",
    label: "Check the basket",
    user: "what’s in my basket?",
    reply: "🛒 Your Basket (6 items) · To Pay ₹272",
  },
  {
    id: "addresses",
    label: "Show my addresses",
    user: "show my addresses",
    reply: "🏠 Your saved addresses · Tap a button to switch, or tell me the label.",
  },
  {
    id: "order",
    label: "Where is my order?",
    user: "where is my order?",
    reply: "You have no active order right now.",
  },
  {
    id: "privacy",
    label: "Delete my data",
    user: "delete my data",
    reply: "Your personal data and Swiggy connection have been permanently deleted.",
  },
] as const;


export const STEPS = [
  {
    title: "Text your list",
    body: "Type it the way you would text a friend. Grocer checks the live store and replies with a basket receipt.",
  },
  {
    title: "Read the basket",
    body: "Prices, fees and the total come back in the chat. Nothing is ordered yet.",
  },
  {
    title: "Check the bill",
    body: "The total is clear before anything else. Payments open next.",
  },
] as const;

export const SAFETY = [
  {
    title: "Only the button can order",
    body: "A text message can never place an order. The Pay button is the only key.",
  },
  {
    title: "Prices are read again",
    body: "Stock and prices are checked at tap time. If anything moved, the order stops before money.",
  },
  {
    title: "One approval, one order",
    body: "A double tap or an old approval bounces off. Nothing runs twice.",
  },
] as const;

export const CAP_NOTE = {
  title: "₹1,000 safety cap",
  body: "Go over it and Grocer waits. You raise the cap yourself, on purpose.",
} as const;

export const FAQS = [
  {
    q: "Is Grocer an official Swiggy app?",
    a: "No. Grocer is an independent app built on Swiggy’s official Instamart tools. Your order and payment stay with Swiggy.",
  },
  {
    q: "Do I need the Swiggy app?",
    a: "No. You need a Swiggy account. The sign-in link opens Swiggy’s page once; after that, everything happens in WhatsApp.",
  },
  {
    q: "How do I connect my Swiggy account?",
    a: "Enter your WhatsApp number on this page. The page opens WhatsApp with a short code. Send it from that number, and the bot replies with a private Swiggy sign-in link. Grocer never asks for your password or UPI PIN.",
  },
  {
    q: "Can I pay yet?",
    a: "Not yet. The chat, live prices, basket, addresses and order answers work today. Payments open next, and checkout stays locked until then.",
  },
  {
    q: "Does Grocer charge me?",
    a: "No fee and no markup. You pay Swiggy’s prices and fees.",
  },
  {
    q: "Where does it work?",
    a: "Anywhere Instamart delivers. Grocer uses the store for your saved address.",
  },
  {
    q: "What if something is out of stock?",
    a: "Grocer tells you and never swaps anything without asking.",
  },
  {
    q: "Where does my data go?",
    a: "Address and basket copies are deleted after 24 hours. The number you type on this page is not stored. Your Swiggy login is encrypted, and “delete my data” removes what Grocer stores.",
  },
] as const;
