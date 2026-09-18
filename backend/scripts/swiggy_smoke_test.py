"""Opt-in Swiggy Instamart MCP smoke test.

The default mode is read-only. Live credentials must be supplied through
``SWIGGY_AUTH_TOKEN``; tokens are never accepted as command-line arguments.

Examples:
    python backend/scripts/swiggy_smoke_test.py
    python backend/scripts/swiggy_smoke_test.py --mock
    python backend/scripts/swiggy_smoke_test.py --login
    python backend/scripts/swiggy_smoke_test.py --allow-cart-mutation

The destructive cart test refuses to run unless the active provider cart is
empty. It verifies ownership of the exact test item before clearing it. This
script never calls checkout and cannot prove that checkout works.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from backend.integrations.commerce.mock_adapter import MockCommerceAdapter
from backend.integrations.commerce.models import CartItemUpdate, CommerceCart, ProductVariant
from backend.integrations.commerce.port import CommercePort


def _print_cart(cart: CommerceCart) -> None:
    """Print a concise, non-secret summary of the active cart."""
    if not cart.items:
        print("-> Active cart is empty.")
        return
    print(f"-> Active cart contains {len(cart.items)} item(s); total ₹{cart.grand_total:.2f}.")
    for item in cart.items:
        print(f"   - {item.name} x{item.quantity}: ₹{item.total_price:.2f}")


def _owns_test_cart(cart: CommerceCart, variant: ProductVariant) -> bool:
    """Return whether the cart contains only the item created by this run."""
    return (
        len(cart.items) == 1
        and cart.items[0].spin_id == variant.spin_id
        and cart.items[0].quantity == 1
    )


async def _read_current_cart(adapter: CommercePort) -> CommerceCart | None:
    print("\n[STEP 4] Reading the active cart without changing it...")
    try:
        cart = await adapter.get_cart()
    except Exception as exc:
        print(f"-> FAILED: get_cart raised {type(exc).__name__}: {exc}")
        return None
    _print_cart(cart)
    return cart


async def _run_destructive_cart_check(
    adapter: CommercePort,
    *,
    address_id: str,
    initial_cart: CommerceCart,
    target_variant: ProductVariant | None,
) -> int:
    """Mutate and restore a cart only when this run can establish ownership."""
    if initial_cart.items:
        print("\nREFUSED: The active cart was not empty before this test.")
        print("No cart changes were made. Empty it yourself only if that is truly intended.")
        return 2
    if target_variant is None:
        print("\nREFUSED: No in-stock catalogue variant was available for the cart test.")
        return 1

    print(f"\n[STEP 5] DESTRUCTIVE: setting the cart to 1 x {target_variant.name}...")
    try:
        await adapter.update_cart(
            items=[
                CartItemUpdate(
                    spin_id=target_variant.spin_id,
                    quantity=1,
                    sku_id=target_variant.sku_id,
                )
            ],
            address_id=address_id,
        )
        verified_cart = await adapter.get_cart()
    except Exception as exc:
        print(f"-> FAILED: cart mutation/read-back raised {type(exc).__name__}: {exc}")
        print("The provider cart may have changed. Inspect it manually before continuing.")
        return 1

    if not _owns_test_cart(verified_cart, target_variant):
        print("-> REFUSED CLEANUP: cart read-back no longer matches the exact test item.")
        print("The cart was not cleared because this run cannot prove it owns the contents.")
        _print_cart(verified_cart)
        return 2

    print("-> Cart mutation verified by read-back.")
    try:
        payment_options = await adapter.get_payment_options(address_id=address_id)
        print(f"-> Read {len(payment_options)} payment option(s); no payment was attempted.")
    except Exception as exc:
        print(f"-> Warning: payment-option read raised {type(exc).__name__}: {exc}")

    print("\n[STEP 6] DESTRUCTIVE: clearing the cart created by this test...")
    try:
        pre_clear_cart = await adapter.get_cart()
        if not _owns_test_cart(pre_clear_cart, target_variant):
            print("-> REFUSED CLEANUP: cart changed after verification; it was not cleared.")
            return 2
        await adapter.clear_cart()
        final_cart = await adapter.get_cart()
    except Exception as exc:
        print(f"-> FAILED: cleanup raised {type(exc).__name__}: {exc}")
        print("Inspect the provider cart manually; cleanup is not confirmed.")
        return 1

    if final_cart.items:
        print("-> FAILED: provider cart is not empty after cleanup.")
        _print_cart(final_cart)
        return 1
    print("-> Cleanup verified: the cart is empty.")
    return 0


async def run_smoke_test(
    token: str | None,
    *,
    is_mock: bool = False,
    query: str = "milk",
    allow_cart_mutation: bool = False,
) -> int:
    """Run read-only provider checks and an optional guarded cart mutation."""
    print("=" * 65)
    print("GROCER — SWIGGY INSTAMART INTEGRATION SMOKE TEST")
    print("=" * 65)

    adapter: CommercePort
    if is_mock:
        print("Mode: MOCK ADAPTER")
        adapter = MockCommerceAdapter()
    else:
        if not token:
            print("ERROR: SWIGGY_AUTH_TOKEN is not set.")
            print("Set it in the environment, or run with --login to start OAuth.")
            return 1
        from backend.integrations.commerce.swiggy_adapter import SwiggyMCPAdapter

        print("Mode: LIVE SWIGGY MCP (credentials loaded from environment)")
        adapter = SwiggyMCPAdapter(auth_token=token)

    print(
        "Safety: CART MUTATION ENABLED"
        if allow_cart_mutation
        else "Safety: READ-ONLY (default; provider state will not be changed)"
    )

    print("\n[STEP 1] Reading saved delivery addresses...")
    try:
        addresses = await adapter.get_addresses("smoke-test-customer")
        print(f"-> Success: found {len(addresses)} saved address(es).")
        for index, address in enumerate(addresses, 1):
            print(f"   [{index}] {address.label or 'Saved address'} ({address.city or 'city unavailable'})")
        if not addresses:
            print("-> FAILED: no saved address is available for address-scoped search.")
            return 1
    except Exception as exc:
        print(f"-> FAILED: get_addresses raised {type(exc).__name__}: {exc}")
        return 1

    selected_address = addresses[0]
    print("\n[STEP 2] Using the first saved address for read-only catalogue search.")

    print(f"\n[STEP 3] Searching the catalogue for {query!r}...")
    target_variant: ProductVariant | None = None
    try:
        products = await adapter.search_products(selected_address.id, query)
        print(f"-> Success: found {len(products)} product(s).")
        for product in products[:3]:
            print(f"   - {product.name} ({product.brand or 'brand unavailable'})")
            for variant in product.variants[:2]:
                print(
                    f"     {variant.name} | {variant.pack_size} | "
                    f"₹{variant.price:.2f} | in stock: {variant.in_stock}"
                )
                if target_variant is None and variant.in_stock:
                    target_variant = variant
    except Exception as exc:
        print(f"-> FAILED: search_products raised {type(exc).__name__}: {exc}")
        return 1

    initial_cart = await _read_current_cart(adapter)
    if initial_cart is None:
        return 1

    if not allow_cart_mutation:
        print("\nREAD-ONLY SMOKE TEST COMPLETED.")
        print("Verified: authentication, addresses, catalogue search, and cart read.")
        print("NOT VERIFIED: cart mutation, checkout, payment, order placement, or tracking.")
        return 0

    result = await _run_destructive_cart_check(
        adapter,
        address_id=selected_address.id,
        initial_cart=initial_cart,
        target_variant=target_variant,
    )
    print("\nDESTRUCTIVE CART TEST COMPLETED." if result == 0 else "\nCART TEST DID NOT COMPLETE.")
    print("CHECKOUT WAS NOT CALLED. Real order placement is NOT verified by this script.")
    return result


async def generate_login_url() -> None:
    """Generate an OAuth PKCE login URL without accepting credentials on the CLI."""
    from backend.integrations.commerce.swiggy_oauth import default_oauth_manager

    print("=" * 65)
    print("SWIGGY OAUTH 2.1 WITH PKCE — AUTHORIZE URL GENERATOR")
    print("=" * 65)
    auth_url, state = await default_oauth_manager.initiate_flow(
        customer_id="smoke-test-user",
        redirect_uri="https://grocerr.vercel.app",
    )
    print("\nOpen this URL in your browser to authenticate with Swiggy:")
    print(f"\n{auth_url}\n")
    print(f"State token: {state}")
    print("Complete the callback through the configured application OAuth route.")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse smoke-test arguments."""
    parser = argparse.ArgumentParser(
        description="Read-only Swiggy Instamart integration smoke test by default."
    )
    parser.add_argument("--mock", action="store_true", help="Use the in-memory mock adapter")
    parser.add_argument("--login", action="store_true", help="Generate a Swiggy OAuth login URL")
    parser.add_argument("--query", default="milk", help="Read-only catalogue search query")
    parser.add_argument(
        "--allow-cart-mutation",
        action="store_true",
        help=(
            "DESTRUCTIVE: replace and clear the active cart only when it starts empty "
            "and exact test ownership can be verified"
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    """Run the selected smoke-test mode."""
    args = parse_args()
    if args.login:
        asyncio.run(generate_login_url())
        return

    token = os.environ.get("SWIGGY_AUTH_TOKEN")
    exit_code = asyncio.run(
        run_smoke_test(
            token=token,
            is_mock=args.mock,
            query=args.query,
            allow_cart_mutation=args.allow_cart_mutation,
        )
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
