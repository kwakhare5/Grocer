# ADR 0010: Session Lifecycle, JIT Checkout Re-Auth, Partial Stock Reorders, and Cold-Start Onboarding

## Context
Production grocery commerce introduces four failure points across user lifecycle boundaries:
1. Shopping sessions retaining lingering cart states post-checkout, confusing subsequent shopping runs.
2. Swiggy OAuth token expiration occurring mid-checkout when a customer attempts to pay. **Amended by Gate 1.1:** Grocer refreshes silently with the stored refresh token first and parks only if the refresh fails.
3. 1-tap reorders ("Your Go-To Items") failing completely if a single frequent SKU is temporarily out of stock.
4. Cold-start shoppers with zero saved addresses attempting catalog queries without a local dark store geofence.

## Decision
1. **Post-Payment Session Reset**: The moment an order transitions to `PLACED`, Grocer archives the completed order snapshot, clears the active basket in PostgreSQL, and resets session memory, ensuring the next customer grocery run starts completely fresh.
2. **JIT Checkout Re-Auth Latch**: If a Swiggy token expires (`401 Unauthorized`) during the Lock 2 checkout verification, Grocer parks the approved checkout in PostgreSQL, sends a 1-tap WhatsApp `[Reconnect Swiggy]` button, and immediately delivers the active `[Pay ₹X]` button upon OAuth completion without rebuilding the cart.
3. **Graceful Partial-Stock Reorders**: When executing 1-tap reorders (`[Add All to Basket]`), available items are added, and out-of-stock items are flagged prominently under a dedicated receipt section (*"Not added: Out of stock today"*), never failing the entire transaction.
4. **Cold-Start Location Grounding**: For new users with zero saved Swiggy addresses (`get_addresses` returns 0), Grocer intercepts shopping queries and initiates location onboarding via a WhatsApp GPS pin or free-text address before attempting catalog search.

## Consequences
- Guaranteed zero cart-state leakage across shopping sessions.
- Seamless recovery from background token expirations at checkout.
- High conversion on repeat reorders despite partial warehouse stockouts.
- 100% store fulfillment validity on first-time customer cold starts.
