# Wallet Advocate Guardrails and Live GPS Tracking Transition

We resolved that coupon auto-application must enforce a strict net-total savings guardrail, and payment completion transitions automatically into live GPS rider tracking on WhatsApp.

## Context & Trade-Offs

1. **Net-Total Savings Guardrail**: Applying a coupon that drops the cart below a dark store's free delivery threshold can cause delivery fees to exceed the discount, making the final bill higher. The Customer Advocate calculates the net effect and refuses to apply coupons that increase the final total, suggesting small staples (under ₹30) to bridge the threshold.
2. **Payment to Tracking Transition**: 1-tap mobile UPI links (`upi://pay`) trigger a 15-second background poller. When Swiggy confirms payment (`ORDER_PLACED` / `RIDER_ASSIGNED`), Grocer immediately delivers the rider's name, ETA, and live tracking map link directly in chat with interactive buttons.
3. **Receipt Formatting**: Total savings are highlighted deterministically on receipt cards with `🎉 *Total Saved:* ₹...`.
