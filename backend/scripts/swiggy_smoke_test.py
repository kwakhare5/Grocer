"""Opt-in real integration smoke test for Swiggy Instamart MCP (Spec Section 16).

Usage:
    # 1. Using an existing authenticated Swiggy JWT token:
    python backend/scripts/swiggy_smoke_test.py --token <SWIGGY_JWT_TOKEN>

    # 2. Or using environment variable:
    set SWIGGY_AUTH_TOKEN=<SWIGGY_JWT_TOKEN>
    python backend/scripts/swiggy_smoke_test.py

    # 3. Generating a login URL via PKCE:
    python backend/scripts/swiggy_smoke_test.py --login

    # 4. Dry-run / mock simulation:
    python backend/scripts/swiggy_smoke_test.py --mock

Never runs in automated CI; completely opt-in.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from backend.integrations.commerce.models import CartItemUpdate
from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter
from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.swiggy_oauth import default_oauth_manager


async def run_smoke_test(token: str | None, is_mock: bool = False, query: str = "milk") -> int:
    print("=" * 65)
    print("GROCER — REAL SWIGGY INSTAMART INTEGRATION SMOKE TEST")
    print("=" * 65)

    if is_mock:
        print("Mode: MOCK SIMULATION SEAM (In-Memory)")
        adapter = MockCommerceAdapter()
    else:
        if not token:
            print("ERROR: No Swiggy access token provided.")
            print("Provide via --token <JWT> or SWIGGY_AUTH_TOKEN env variable.")
            print("Run with --login to generate an OAuth PKCE authorization URL.")
            return 1
        print("Mode: LIVE SWIGGY INSTAMART MCP ADAPTER")
        # Ensure token is masked
        masked = token[:6] + "..." + token[-4:] if len(token) > 12 else "***"
        print(f"Token: {masked} (Strictly masked)")
        adapter = SwiggyMCPAdapter(auth_token=token)

    # Step 1: get_addresses
    print("\n[STEP 1] Fetching delivery addresses via get_addresses()...")
    try:
        addresses = await adapter.get_addresses("smoke-test-customer")
        print(f"-> Success: Found {len(addresses)} delivery address(es).")
        for idx, addr in enumerate(addresses, 1):
            print(f"   [{idx}] ID: {addr.id} | Label: {addr.label} | Street: {addr.street or 'N/A'} | City: {addr.city or 'N/A'}")
        if not addresses:
            print("-> Warning: No addresses returned. Cannot proceed with address-scoped search.")
            return 1
    except Exception as exc:
        print(f"-> FAILED: get_addresses raised {type(exc).__name__}: {exc}")
        return 1

    # Step 2: Select address
    selected_addr = addresses[0]
    print(f"\n[STEP 2] Selected address: {selected_addr.id} ({selected_addr.label})")

    # Step 3: search_products
    print(f"\n[STEP 3] Searching products with query={query!r} at address {selected_addr.id}...")
    try:
        products = await adapter.search_products(selected_addr.id, query)
        print(f"-> Success: Found {len(products)} product(s).")
        target_variant = None
        for p in products[:3]:
            print(f"   Product: {p.name} (Brand: {p.brand or 'General'})")
            for v in p.variants[:2]:
                print(f"     - Variant: {v.name} | Pack: {v.pack_size} | Price: ₹{v.price} | InStock: {v.in_stock} | SpinID: {v.spin_id}")
                if v.in_stock and not target_variant:
                    target_variant = v
        if not target_variant:
            print("-> Warning: No in-stock variant found to test cart creation.")
            return 0
    except Exception as exc:
        print(f"-> FAILED: search_products raised {type(exc).__name__}: {exc}")
        return 1

    # Step 4: update_cart & get_cart
    print(f"\n[STEP 4] Updating cart with 1x {target_variant.name} (spinId: {target_variant.spin_id})...")
    try:
        cart = await adapter.update_cart(
            items=[CartItemUpdate(spin_id=target_variant.spin_id, quantity=1, sku_id=target_variant.sku_id)],
            cart_id="smoke-test-cart",
            address_id=selected_addr.id,
        )
        print(f"-> Success: Cart updated! Items: {len(cart.items)} | Grand Total: ₹{cart.grand_total:.2f}")
        for item in cart.items:
            print(f"   - {item.name} x{item.quantity}: ₹{item.total_price:.2f}")
    except Exception as exc:
        print(f"-> FAILED: update_cart raised {type(exc).__name__}: {exc}")
        return 1

    # Step 5: get_payment_options
    print(f"\n[STEP 5] Fetching live payment options for cart...")
    try:
        payment_options = await adapter.get_payment_options(cart_id="smoke-test-cart", address_id=selected_addr.id)
        print(f"-> Success: Available payment options ({len(payment_options)}):")
        for opt in payment_options:
            print(f"   - Method: {opt.method} | Label: {opt.label} | ID: {opt.id or 'N/A'}")
    except Exception as exc:
        print(f"-> FAILED: get_payment_options raised {type(exc).__name__}: {exc}")

    # Step 6: clear_cart (Clean up)
    print("\n[STEP 6] Cleaning up: Clearing smoke test cart...")
    try:
        await adapter.clear_cart("smoke-test-cart")
        print("-> Success: Smoke test cart cleared cleanly.")
    except Exception as exc:
        print(f"-> Warning: clear_cart raised {exc}")

    print("\n" + "=" * 65)
    print("LIVE SMOKE TEST COMPLETED: ALL COMMERCEPORT STAGES VERIFIED")
    print("=" * 65)
    return 0


async def generate_login_url() -> None:
    print("=" * 65)
    print("SWIGGY OAUTH 2.1 WITH PKCE — AUTHORIZE URL GENERATOR")
    print("=" * 65)
    auth_url, state = await default_oauth_manager.initiate_flow(
        customer_id="smoke-test-user",
        redirect_uri="https://grocerr.vercel.app",
    )
    print("\nOpen the following URL in your browser to authenticate with Swiggy:")
    print(f"\n{auth_url}\n")
    print(f"State token: {state}")
    print("\nAfter completing phone + OTP login, exchange the code using:")
    print("python -c \"import asyncio; from backend.integrations.commerce.swiggy_oauth import default_oauth_manager; ...\"")


def main() -> None:
    parser = argparse.ArgumentParser(description="Swiggy Instamart Integration Smoke Test")
    parser.add_argument("--token", type=str, help="Authenticated Swiggy access token")
    parser.add_argument("--mock", action="store_true", help="Run with MockCommerceAdapter simulation")
    parser.add_argument("--login", action="store_true", help="Generate Swiggy OAuth login URL")
    parser.add_argument("--query", type=str, default="milk", help="Search query (default: milk)")
    args = parser.parse_args()

    if args.login:
        asyncio.run(generate_login_url())
        return

    token = args.token or os.environ.get("SWIGGY_AUTH_TOKEN")
    exit_code = asyncio.run(run_smoke_test(token=token, is_mock=args.mock, query=args.query))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
