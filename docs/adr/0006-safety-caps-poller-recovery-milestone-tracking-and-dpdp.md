# ADR 0006: Family Account Safety Cap, Milestone Hygiene, and DPDP Data Erasure

## Context
1. **Shared Devices & Rogue Orders:** In Indian households, phones are frequently shared with children, family members, or left unlocked on work desks. Unrestricted conversational bots risk accidental multi-thousand-rupee orders from joke texts or toddler taps.
2. **Notification Spam Fatigue:** Delivery bots that emit updates for every minor status change annoy customers and cause WhatsApp mutes or blocks.
3. **Privacy Rights:** Indian DPDP regulations require customer delivery addresses and shopping patterns to be minimized and erasable upon request.

## Decision
1. **Launch-Gated ₹1,000 Family Safety Cap**: Grocer establishes a default hard cap of ₹1,000 per order during launch. If a basket exceeds ₹1,000, direct payment is held and an interactive WhatsApp button is presented: `[Confirm Large Order: ₹X]`, preventing accidental high-value checkouts.
2. **Respectful 3-Milestone Tracking**: Outbound delivery notifications are restricted strictly to three physical milestones:
   - Milestone 1: *Order confirmed & packing*
   - Milestone 2: *Rider picked up & on the way (with clickable live GPS map link)*
   - Milestone 3: *Delivered*
3. **24-Hour DPDP Data Minimization & Erasure**: Personal customer delivery addresses and line-item basket snapshots are permanently deleted from database storage 24 hours post-order. Minimal transaction audit metadata is retained for 90 days. An explicit inbound message `"delete my data"` instantly purges all customer records and revokes active Swiggy OAuth tokens.

## Consequences
- Guaranteed protection against accidental high-value orders on shared devices.
- Respectful WhatsApp notification hygiene that customers keep unmuted.
- Full compliance with Indian DPDP statutory requirements.
