"""
Services module for external app integrations.

This module provides clean interfaces to optional external apps,
with graceful fallbacks when they're not installed.
"""

from pos_next.services.barcode import (
    compute_resolved_item_data,
    is_barcode_resolver_available,
    parse_internal_scale_barcode,
    resolve_barcode,
    resolve_internal_scale_barcode,
)

__all__ = [
    "resolve_barcode",
    "resolve_internal_scale_barcode",
    "parse_internal_scale_barcode",
    "is_barcode_resolver_available",
    "compute_resolved_item_data",
]
