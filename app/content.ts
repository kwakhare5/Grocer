export const NAV = [
  { label: "What it does", href: "/#what" },
  { label: "Safety", href: "/#safety" },
  { label: "Built", href: "/#built" },
  { label: "FAQ", href: "/#faq" },
] as const;

export const SAMPLE = {
  message: "milk, eggs, bread, paneer, butter, tomatoes",
  time: "Today · 9:41",
  count: "6 products",
  items: [
    { name: "Farm Fresh Milk 500 ml", qty: "×2", price: "₹64" },
    { name: "Eggs (6)", qty: "×1", price: "₹60" },
    { name: "Brown bread 400 g", qty: "×1", price: "₹45" },
    { name: "Paneer 200 g", qty: "×1", price: "₹89" },
    { name: "Butter 100 g", qty: "×1", price: "₹58" },
    { name: "Tomatoes 500 g", qty: "×1", price: "₹27" },
  ],
  itemTotal: "₹343.00",
  couponLabel: "Sample coupon",
  couponAmount: "− ₹40.00",
  handling: "₹9.00",
  delivery: "FREE",
  toPay: "₹312",
  capLabel: "₹312 of ₹1,000",
  capWidth: "31%",
} as const;

export const CAPABILITIES = [
  {
    name: "Build the basket",
    line: "Add, swap or clear items in a plain sentence.",
    status: "Live",
    tone: "live",
  },
  {
    name: "Ask about prices",
    line: "Prices, stock and coupons, read live from Swiggy.",
    status: "Live",
    tone: "live",
  },
  {
    name: "Plan dinner",
    line: "Say “dinner for four” and get a priced ingredient list you can add in one tap.",
    status: "In testing",
    tone: "testing",
  },
  {
    name: "Keep your addresses",
    line: "List, switch, add or remove a saved address without opening another app.",
    status: "In testing",
    tone: "testing",
  },
  {
    name: "Follow the rider",
    line: "Live order status and ETA, in the same thread as the basket.",
    status: "In testing",
    tone: "testing",
  },
  {
    name: "Pay once",
    line: "Tap Pay, then finish by UPI on Swiggy’s own secure page.",
    status: "Opening next",
    tone: "next",
  },
] as const;

export const STEPS = [
  {
    title: "You tap Pay.",
    body: "A text can’t order. Only the Pay button can.",
  },
  {
    title: "We re-read the basket.",
    body: "Live prices, live stock. If something moved or sold out, you see it before paying.",
  },
  {
    title: "It runs once.",
    body: "One approval, one order. A double tap bounces off.",
  },
] as const;

export const BUILT = [
  {
    title: "Swiggy tools, connected",
    body: "Browse, basket, orders, addresses, tracking, coupons. Every Instamart tool is covered: most from chat, the rest with a clear “not supported”.",
    big: "20",
  },
  {
    title: "Live shelf, live price",
    body: "Prices and stock come from a live Swiggy read, not a saved catalogue.",
  },
  {
    title: "Coupons that actually save",
    body: "Grocer tries up to two applicable coupons, keeps only one that lowers your total, and shows the rupees saved.",
  },
  {
    title: "Once-only checkout",
    body: "An approval is tied to you and to one basket snapshot. It cannot be replayed by anyone else.",
  },
  {
    title: "A cap you control",
    body: "Baskets above ₹1,000 wait until you raise the cap yourself.",
  },
  {
    title: "Forgets in 24 hours",
    body: "Basket and address copies are set to expire after a day. “Delete my data” deletes what Grocer stores about you, and your Swiggy token stays encrypted.",
  },
] as const;

export const FAQS = [
  {
    q: "Is Grocer an official Swiggy product?",
    a: "No. Grocer is an independent client built on Swiggy’s official Instamart developer interface. Your order and payment stay with Swiggy.",
  },
  {
    q: "How do I connect my Swiggy account?",
    a: "Once, from a private link the bot sends you. You sign in on Swiggy’s page with your Swiggy account. Grocer never asks for your password or UPI PIN.",
  },
  {
    q: "Can I pay yet?",
    a: "Not yet. Checkout is the last step we are finishing. The chat, live prices and basket work today; payments open next.",
  },
  {
    q: "Do I pay anything to Grocer?",
    a: "No fee and no markup. You pay Swiggy’s item prices, delivery, handling and taxes.",
  },
  {
    q: "What if an item is out of stock?",
    a: "Grocer names the item and offers Swiggy’s real alternative when one exists. It never swaps anything silently.",
  },
  {
    q: "Where does my data go?",
    a: "Basket and address copies are set to expire after 24 hours. Your Swiggy token is encrypted, and “delete my data” deletes what Grocer stores about you.",
  },
] as const;
