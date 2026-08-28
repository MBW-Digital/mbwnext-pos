"""
Barcode resolver service for POS Next.

This module integrates optional barcode_resolver rules (weighted/priced barcodes) and a built-in
parser for fixed-layout electronic-scale labels when that app is not used.

When barcode_resolver is not installed, :func:`parse_internal_scale_barcode` still enables
15-digit labels: prefix + **7-digit PLU** + weight (grams) + check digit (see function docstring).
"""

from __future__ import annotations

from functools import lru_cache
from typing import FrozenSet, TypedDict

import frappe
from erpnext.stock.get_item_details import get_conversion_factor

# Two-digit prefixes that identify "scale / weighted" internal barcodes (configurable later via POS Settings).
_DEFAULT_SCALE_PREFIXES: FrozenSet[str] = frozenset({"21"})


class BarcodeResult(TypedDict, total=False):
    """Type definition for barcode resolution result."""

    item_barcode: str  # The barcode from Item Barcodes table
    integer_value: str  # Integer part of the encoded value
    decimal_value: str  # Decimal part of the encoded value
    barcode_type: str  # "Weighted" or "Priced"
    uom: str | None  # UOM from Item Barcodes table
    qty: float | None  # Quantity (only for weighted barcodes)


class ResolvedItemData(TypedDict, total=False):
    """Type definition for resolved item data to be applied to cart."""

    resolved_qty: float | None
    resolved_uom: str | None
    resolved_price: float | None
    resolved_barcode_type: str | None


@lru_cache(maxsize=1)
def is_barcode_resolver_available() -> bool:
    """
    Check if the barcode_resolver app is installed.

    Returns:
        bool: True if barcode_resolver is available, False otherwise.

    Note:
        Result is cached for performance. Server restart clears the cache.
    """
    return "barcode_resolver" in frappe.get_installed_apps()


def resolve_barcode(barcode: str, pos_profile: str) -> BarcodeResult | None:
    """
    Resolve a barcode using the barcode_resolver app if available.

    This function attempts to parse special barcode formats (weighted/priced)
    using configurable rules from the barcode_resolver app.

    Args:
        barcode: The barcode string to resolve.

    Returns:
        BarcodeResult dict if the barcode matches a rule, None otherwise.
        Also returns None if barcode_resolver app is not installed.

    Example:
        >>> result = resolve_barcode("2001234001500")
        >>> if result:
        ...     print(f"Item: {result['item_barcode']}, Qty: {result['qty']}")
    """
    if not is_barcode_resolver_available():
        return None

    try:
        from barcode_resolver.barcode_resolver.doctype.barcode_rule.utils import (
            resolve_barcode as _resolve_barcode,
        )
        # get POS Settings
        pos_settings = frappe.get_doc("POS Settings", {"pos_profile": pos_profile})
        barcode_rules = [rule.barcode_rule for rule in pos_settings.barcode_rules if not rule.disable]
        return _resolve_barcode(barcode, barcode_rules)
    except ImportError:
        # App might have been uninstalled, clear cache and return None
        is_barcode_resolver_available.cache_clear()
        return None
    except Exception:
        # Log unexpected errors but don't break POS functionality
        frappe.log_error(
            title="Barcode Resolver Error",
            message=f"Error resolving barcode: {barcode}",
        )
        return None


def _weight_grams_to_integer_decimal_parts(grams: int) -> tuple[str, str]:
    """Build integer_value / decimal_value strings like the barcode_resolver weighted format."""
    kg = grams / 1000.0
    text = f"{kg:.10f}".rstrip("0").rstrip(".")
    if "." in text:
        a, b = text.split(".", 1)
        return a, b
    return text, "0"


def parse_internal_scale_barcode(
    barcode: str,
    allowed_prefixes: FrozenSet[str] | None = None,
) -> BarcodeResult | None:
    """
    Parse fixed-layout scale barcode (electronic scale label) without barcode_resolver app.

    Layout (digits only, **15 characters total**):
    PP (2) + **mã hàng / PLU (7)** + trọng lượng gam (5) + ký tự kiểm tra (1).

    Example với PLU ``4261097`` và nặng ``1.25 kg`` (1250 g):
    Tem **15 số**: ``214261097012505`` → tiền tố ``21``, mã ``4261097``, khối ``01250`` (gam),
    ký tự kiểm ``5``. Trên Item phải có **Item Barcode** đúng ``4261097``.

    Example khác (PLU có số 0 đầu): ``210000100012505`` → PLU ``0000100``, ``01250`` g → 1.25 kg.

    Weight field is interpreted as integer grams (01250 → 1250 g).
    Check digit is not validated (many retail scales use non-GS1 check algorithms).
    """
    prefixes = allowed_prefixes if allowed_prefixes is not None else _DEFAULT_SCALE_PREFIXES
    raw = (barcode or "").strip()
    if not raw.isdigit():
        return None

    if len(raw) != 15:
        return None

    prefix, article, weight_str, _check = raw[0:2], raw[2:9], raw[9:14], raw[14]

    if prefix not in prefixes:
        return None

    # Reject all-zero PLU (invalid); leading zeros like 0000100 are valid.
    if set(article) == {"0"}:
        return None

    try:
        grams = int(weight_str)
    except ValueError:
        return None

    if grams <= 0:
        return None

    int_part, dec_part = _weight_grams_to_integer_decimal_parts(grams)

    return {
        "item_barcode": article,
        "integer_value": int_part,
        "decimal_value": dec_part,
        "barcode_type": "Weighted",
        "qty": grams / 1000.0,
        "uom": frappe.db.get_value("Item Barcode", {"barcode": article}, "uom"),
    }


def resolve_internal_scale_barcode(barcode: str, pos_profile: str) -> BarcodeResult | None:
    """
    Apply internal scale barcode parsing when the optional barcode_resolver app is absent or unused.

    Args:
        barcode: Scanned value from the scale label.
        pos_profile: Reserved for future per-profile prefix overrides.

    Returns:
        BarcodeResult compatible dict, or None if the string does not match.
    """
    del pos_profile  # future: POS Settings overrides
    return parse_internal_scale_barcode(barcode)


def compute_resolved_item_data(
    resolved_barcode: BarcodeResult | None,
    item,
) -> ResolvedItemData | None:
    """
    Compute qty and uom from resolved barcode data.

    For weighted barcodes: uses qty directly from the barcode.
    For priced barcodes: computes qty = encoded_price / item_rate.

    Args:
        resolved_barcode: The result from resolve_barcode().
        item_rate: The item's unit price (required for priced barcodes).

    Returns:
        ResolvedItemData with resolved_qty, resolved_uom, and resolved_barcode_type,
        or None if no valid resolution.

    Example:
        >>> resolved = resolve_barcode("2001234001500")
        >>> if resolved:
        ...     item_data = compute_resolved_item_data(resolved, item_rate=10.0)
        ...     print(f"Qty: {item_data['resolved_qty']}, UOM: {item_data['resolved_uom']}")
    """
    if not resolved_barcode:
        return None

    barcode_type = resolved_barcode.get("barcode_type")
    barcode_uom = resolved_barcode.get("uom")
    uom_prices = item.get("uom_prices", {})
    barcode_uom_price = uom_prices.get(barcode_uom) if barcode_uom else None
    item_uom = item.get("uom")
    item_price = item.get("rate")

    item_code_for_conv = item.get("name") or item.get("item_code")

    integer_value = resolved_barcode.get("integer_value", "0")
    decimal_value = resolved_barcode.get("decimal_value", "0")

    is_weighted = barcode_type == "Weighted"
    if not is_weighted and is_barcode_resolver_available():
        from barcode_resolver.barcode_resolver.doctype.barcode_rule.utils import BarcodeTypes

        is_weighted = barcode_type == BarcodeTypes.WEIGHTED.value

    if is_weighted:
        qty = float(f"{integer_value}.{decimal_value}")
        uom = barcode_uom
        price = barcode_uom_price
        if barcode_uom and barcode_uom not in uom_prices:
            conversion_factor = get_conversion_factor(
                item_code_for_conv, barcode_uom
            ).get("conversion_factor", 1)
            qty *= conversion_factor
            uom = item_uom
            price = item_price
        elif not barcode_uom:
            uom = item_uom
            price = item_price

        return {
            "resolved_qty": qty,
            "resolved_uom": uom,
            "resolved_price": price,
            "resolved_barcode_type": barcode_type,
        }

    if not is_barcode_resolver_available():
        return None

    from barcode_resolver.barcode_resolver.doctype.barcode_rule.utils import BarcodeTypes

    if barcode_type == BarcodeTypes.PRICED.value:
        encoded_price = float(f"{integer_value}.{decimal_value}")
        if barcode_uom in uom_prices:
            barcode_uom_price = uom_prices.get(barcode_uom)
            price = barcode_uom_price
            uom = barcode_uom
            qty = encoded_price / price if price and price > 0 else None
        else:
            conversion_factor = get_conversion_factor(
                item_code_for_conv, barcode_uom
            ).get("conversion_factor", 1)
            uom = item_uom
            price = conversion_factor * item_price
            qty = encoded_price / price if price and price > 0 else None
        return {
            "resolved_qty": qty,
            "resolved_uom": uom,
            "resolved_price": encoded_price,
            "resolved_barcode_type": barcode_type,
        }

    return None
