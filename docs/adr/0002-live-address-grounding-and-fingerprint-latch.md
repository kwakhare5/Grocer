# Live Address Grounding and Normalized 2-Decimal Fingerprint Latch

We resolved that customer delivery addresses must be strictly grounded in the customer's live Swiggy account with in-chat creation and activation via Swiggy MCP `create_address`. Furthermore, cart SHA-256 fingerprinting must normalize all monetary quantities to standard 2-decimal strings (`f"{float(val):.2f}"`).

## Context & Trade-Offs

Previously, the system risked referencing fictitious or hardcoded neighborhood names and suffered from subtle floating-point string mismatches (e.g. `Decimal("150.0")` vs `Decimal("150")`), which caused the cryptographic 3-lock checkout gate to falsely reject valid orders with `"CART_CHANGED"`.

By grounding addresses in live Swiggy MCP data, users can provide an address or drop a WhatsApp location pin and have it saved directly to their Swiggy account without leaving the chat. By standardizing currency amounts to 2 decimal places before hashing, the cart fingerprint remains 100% deterministic across integer and float representations.
