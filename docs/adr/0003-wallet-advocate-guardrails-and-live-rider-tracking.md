# ADR 0003: The Wallet Champion Promise, HTTPS Mobile Payments, and Live GPS Tracking

> **Status 2026-10-27:** Active with gaps. The coupon guard works, but the savings message is not sent, and tracking does not call `track_order`. See `STATUS.md` P0 #7 and P1.

## Context
1. **The Coupon Trap:** Grocery shoppers in India love discounts, but quick-commerce coupons often carry minimum spend cutoffs. If applying a ₹50 discount drops a cart from ₹210 to ₹160, Swiggy slaps a ₹60 delivery fee on the order, increasing the final payable total from ₹210 to ₹220. The customer used a coupon and ended up paying MORE money.
2. **Mobile Payment Restrictions:** Meta WhatsApp Cloud API strictly rejects custom deep-link URL schemes (`upi://`) in interactive CTA URL buttons. Swiggy Instamart MCP officially provides an authoritative HTTPS payment link (`data.bridgeUrl`) rendering a mobile tap-to-pay and desktop QR interface.
3. **Tracking Anxiety:** Post-payment, customers suffer delivery anxiety when delivery apps fall silent or emit overwhelming high-frequency spam.

## Decision
1. **The Wallet Champion Promise**: Grocer acts as the customer's personal financial advocate. It calculates the net payable effect of Swiggy coupons:
   - If applying a coupon increases the final payable total (or leaves it unchanged due to delivery fee shifts), Grocer rejects the coupon, restores baseline prices, and explains clearly on the receipt: *"Coupon INSTA50 gives ₹50 off, but triggers a ₹60 delivery fee. I skipped it to keep your total ₹10 cheaper."*
   - Real rupee savings are prominently highlighted on the receipt (`🎉 *You saved ₹X on this order!*`).
2. **Authoritative HTTPS BridgeUrl Payment Button**: Checkout delivers Swiggy's official `data.bridgeUrl` inside a WhatsApp CTA URL button: `[Pay ₹X (UPI / Card)]`. Tapping opens Swiggy's mobile payment screen with direct intent handoff to Google Pay, PhonePe, Paytm, or cards.
3. **Durable 5-Minute Long-Poll & Real-Time GPS Tracking**:
   - A background poller checks payment status using Swiggy's long-poll intervals (~19s) up to the official 5-minute cap (`maxTimeToPollForInMs`), resilient to mobile app switching.
   - Upon confirmed settlement (`success`/`paid`), Grocer transitions immediately to live GPS tracking via `track_order`, pushing the rider's name, ETA, and live tracking map link directly to WhatsApp.

## Consequences
- Customers never get tricked into paying higher totals by counter-productive coupons.
- 100% compliance with WhatsApp interactive button URL standards.
- Seamless mobile payment handoff with zero chat-level dropouts.
- Transparent, respectful post-order rider visibility.
