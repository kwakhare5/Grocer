# ADR 0006: Safety Caps, Durable Poller Recovery, Milestone Tracking, and DPDP Data Privacy

## Context
1. Production launch of an automated grocery commerce engine carries financial liability if unrestricted carts or bulk orders fail unexpectedly.
2. In real-world Indian mobile commerce, UPI transactions frequently experience transient network dropouts or app switches where the user completes payment in GPay/PhonePe but fails to redirect back to WhatsApp.
3. Chat messaging fatigue occurs when delivery bots emit excessive high-frequency location updates.
4. Indian DPDP regulations and Swiggy's Data Processing terms require data minimization, safe cryptographic handling, and user deletion rights.

## Decision
1. **Launch-Gated ₹1,000 Safety Cap**: Grocer establishes a default hard cap of ₹1,000 per order during initial rollout. If a cart exceeds this threshold, direct checkout is held and an interactive WhatsApp button is presented: `[Raise Limit to ₹2,000]`.
2. **Durable Payment Recovery Poller**: Grocer runs a persistent PostgreSQL-backed poller (`FOR UPDATE SKIP LOCKED`) watching `check_payment_status` for up to 5 minutes post-checkout. When Swiggy confirms server-side settlement, Grocer immediately pushes an authoritative confirmation receipt to the customer's WhatsApp chat, irrespective of browser/app dropouts.
3. **Milestone-Only Rider Tracking**: Outbound delivery notifications are restricted to three discrete physical milestones:
   - Milestone 1: *Order confirmed & packed*
   - Milestone 2: *Rider picked up & out for delivery* (with clickable Swiggy GPS tracking link)
   - Milestone 3: *Delivered*
4. **24-Hour DPDP Data Minimization & Erasure**: Personal customer delivery addresses and line-item basket snapshots are permanently deleted from database storage 24 hours post-order. Minimal transaction audit metadata (transaction ID, paise total, timestamp) is retained for 90 days. An explicit inbound command `"delete my data"` permanently purges all user records and revokes active Swiggy OAuth tokens immediately.

## Consequences
- Guaranteed zero financial overrun during rollout.
- 100% payment reconciliation resilience against mobile disconnections.
- Respectful WhatsApp notification hygiene.
- Full compliance with Indian DPDP statutory requirements and Swiggy Data Fiduciary terms.
