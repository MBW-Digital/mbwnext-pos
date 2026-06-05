import json

import frappe
from frappe.utils import cint, parse_json
from erpnext.stock.get_item_details import get_item_tax_map


def _selling_item_tax_template_names(company):
    """Set name các Item Tax Template được đánh dấu Selling cho công ty (custom field for_selling)."""
    if not company:
        return set()
    if not hasattr(frappe.local, "_mbw_selling_item_tax_names"):
        frappe.local._mbw_selling_item_tax_names = {}
    cache = frappe.local._mbw_selling_item_tax_names
    if company in cache:
        return cache[company]
    if not frappe.db.has_column("Item Tax Template", "for_selling"):
        cache[company] = set()
        return cache[company]
    rows = frappe.get_all(
        "Item Tax Template",
        filters={"company": company, "disabled": 0, "for_selling": 1},
        pluck="name",
    )
    names = set(rows or [])
    cache[company] = names
    return names


def _first_selling_tax_template_for_item(item_code, selling_names):
    if not item_code or not selling_names:
        return None
    item = frappe.get_cached_doc("Item", item_code)
    for row in item.get("taxes") or []:
        tpl = row.get("item_tax_template")
        if tpl and tpl in selling_names:
            return tpl
    return None


def ensure_selling_item_tax_for_item_line(item_code, company, item_tax_template=None, item_tax_rate=None):
    """Trả về (template, item_tax_rate_json) thuế bán; giữ nguyên nếu đã đúng.

    Dùng cho POS get_item_detail để đồng bộ client script set_selling_tax_from_item.
    """
    if not item_code or not company:
        return item_tax_template, item_tax_rate
    selling = _selling_item_tax_template_names(company)
    if not selling:
        return item_tax_template, item_tax_rate
    if item_tax_template and item_tax_template in selling:
        return item_tax_template, item_tax_rate
    replacement = _first_selling_tax_template_for_item(item_code, selling)
    if not replacement:
        return item_tax_template, item_tax_rate
    return replacement, get_item_tax_map(company, replacement, as_json=True)


def _ensure_pos_sales_taxes_rows(doc):
    """Bổ sung dòng Sales Taxes and Charges từ item_tax_rate cho POS.

    ERPNext `set_taxes_and_charges()` return sớm khi is_pos nên không gọi
    `append_taxes_from_item_tax_template()` — calculate_taxes() cần ít nhất một dòng taxes.
    """
    if not cint(doc.get("is_pos")):
        return

    company = doc.company
    for line in doc.items:
        if line.get("item_tax_template") and not line.get("item_tax_rate"):
            line.item_tax_rate = get_item_tax_map(company, line.item_tax_template, as_json=True)

    if doc.get("taxes"):
        return

    for line in doc.items:
        raw = line.get("item_tax_rate")
        if not raw:
            continue
        if isinstance(raw, str):
            try:
                tax_map = parse_json(raw)
            except Exception:
                try:
                    tax_map = json.loads(raw)
                except Exception:
                    continue
        elif isinstance(raw, dict):
            tax_map = raw
        else:
            continue
        if not tax_map:
            continue
        for account_head in tax_map:
            if not account_head:
                continue
            exists = any(t.account_head == account_head for t in doc.get("taxes") or [])
            if not exists:
                doc.append(
                    "taxes",
                    {
                        "charge_type": "On Net Total",
                        "account_head": account_head,
                        "rate": 0,
                        "description": account_head,
                        "set_by_item_tax_template": 1,
                        "category": "Total",
                        "add_deduct_tax": "Add",
                    },
                )


def apply_selling_item_tax_templates(doc, method=None):
    """API/POS không chạy Form JS — ép item_tax_template/item_tax_rate thuế đầu ra trước khi validate.

    Giống logic set_selling_tax_from_item trong controllers/js/sales_invoice.js.
    """
    if doc.doctype != "Sales Invoice" or getattr(doc, "is_return", 0):
        return
    if not doc.company or not doc.get("items"):
        return

    selling = _selling_item_tax_template_names(doc.company)
    if selling:
        changed = False
        for row in doc.items:
            if not row.get("item_code"):
                continue
            curr = row.get("item_tax_template")
            if curr and curr in selling:
                continue
            replacement = _first_selling_tax_template_for_item(row.item_code, selling)
            if not replacement or replacement == curr:
                continue
            row.item_tax_template = replacement
            row.item_tax_rate = get_item_tax_map(doc.company, replacement, as_json=True)
            changed = True

        if changed:
            # Bỏ bảng thuế cũ để calculate_taxes_and_totals dựng lại theo item_tax_rate mới
            doc.set("taxes", [])

    # POS: luôn đảm bảo có child table taxes (ERPNext bỏ qua khi is_pos)
    if cint(doc.get("is_pos")):
        _ensure_pos_sales_taxes_rows(doc)