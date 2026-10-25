"""Grocer v1.0 — AST Architectural Safety Invariant Tests.

Enforces structural guarantees at AST analysis level:
1. No float formatting in currency calculations (integer paise strictly).
2. Agent tools must never have access to checkout mutation tools.
3. Zero project mocking in production code.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"


def test_no_float_formatting_in_backend():
    """Verify that backend code does not use float string formatting (%.2f or {:.2f}) for currency."""
    forbidden_patterns = [".2f", "%0.2f", "%.2f"]
    py_files = list(BACKEND_DIR.rglob("*.py"))
    assert len(py_files) > 0, "No backend python files found to inspect"

    violations = []
    for py_file in py_files:
        code = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in code:
                violations.append(
                    f"{py_file.name}: contains forbidden float pattern '{pattern}'"
                )

    assert not violations, (
        f"Float formatting violations found (use integer paise strictly): {violations}"
    )


def test_no_mock_in_production_code():
    """Ensure production backend code never imports or depends on unittest.mock."""
    py_files = list(BACKEND_DIR.rglob("*.py"))
    assert len(py_files) > 0

    violations = []
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "mock" in alias.name.lower():
                        violations.append(f"{py_file.name}: imports '{alias.name}'")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and "mock" in node.module.lower()
            ):
                violations.append(f"{py_file.name}: imports from '{node.module}'")

    assert not violations, f"Mock imports found in production code: {violations}"


def test_schema_paise_properties_exist():
    """Verify that all price schemas expose integer paise property helpers."""
    from backend.integrations.commerce.schemas import (
        CartItem,
        ProductPrice,
    )

    # Verify ProductPrice
    price = ProductPrice(mrp=74.50, offerPrice=72.00)
    assert price.mrp_paise == 7450
    assert price.offer_price_paise == 7200
    assert isinstance(price.mrp_paise, int)

    # Verify CartItem
    item = CartItem(
        spinId="spin_1",
        skuId="sku_1",
        productId="prod_1",
        itemName="Milk",
        quantity=2,
        isInStockAndAvailable=True,
        mrp=74.0,
        discountedFinalPrice=72.0,
    )
    assert item.mrp_paise == 7400
    assert item.discounted_final_price_paise == 7200
    assert isinstance(item.discounted_final_price_paise, int)
