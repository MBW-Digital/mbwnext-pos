# Copyright (c) 2021, Youssef Restom and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import strip, flt
from frappe.utils import getdate, today


class POSCoupon(Document):
    def autoname(self):
        self.coupon_name = strip(self.coupon_name)
        self.name = self.coupon_name

        if not self.coupon_code:
            if self.coupon_type == "Promotional":
                self.coupon_code = "".join(i for i in self.coupon_name if not i.isdigit())[0:8].upper()
            elif self.coupon_type == "Gift Card":
                self.coupon_code = frappe.generate_hash()[:10].upper()

    def validate(self):
        # Gift Card validations
        if self.coupon_type == "Gift Card":
            self.maximum_use = 1
            if not self.customer:
                frappe.throw(_("Please select the customer for Gift Card."))

        # Discount validations
        if not self.discount_type:
            frappe.throw(_("Discount Type is required"))

        if self.discount_type == "Percentage":
            if not self.discount_percentage:
                frappe.throw(_("Discount Percentage is required"))
            if flt(self.discount_percentage) <= 0 or flt(self.discount_percentage) > 100:
                frappe.throw(_("Discount Percentage must be between 0 and 100"))
        elif self.discount_type == "Amount":
            if not self.discount_amount:
                frappe.throw(_("Discount Amount is required"))
            if flt(self.discount_amount) <= 0:
                frappe.throw(_("Discount Amount must be greater than 0"))

        # Minimum amount validation
        if self.min_amount and flt(self.min_amount) < 0:
            frappe.throw(_("Minimum Amount cannot be negative"))

        # Maximum discount validation
        if self.max_amount and flt(self.max_amount) <= 0:
            frappe.throw(_("Maximum Discount Amount must be greater than 0"))

        # Date validations
        if self.valid_from and self.valid_upto:
            if getdate(self.valid_from) > getdate(self.valid_upto):
                frappe.throw(_("Valid From date cannot be after Valid Until date"))



def customer_has_used_coupon(customer, coupon_code):
    """Đã có hoá đơn nào của khách này dùng mã đó chưa (dùng cho luật one_use).

    Chỗ DUY NHẤT ghi lại một mã đã được dùng là bảng con `POS Coupon Applied`
    trên Sales Invoice. Bản cũ đếm doctype `POS Invoice` — doctype mà app này
    KHÔNG BAO GIỜ ghi vào (0 bản ghi, trong khi POS đã xuất 203 hoá đơn Sales
    Invoice) — nên luật "một lần mỗi khách" chưa từng chặn ai. Cũng không lọc
    thẳng trên Sales Invoice được vì bảng đó không hề có cột `coupon_code`;
    invoices.py có gán `invoice_doc.coupon_code` nhưng không có cột nên giá trị
    đó rơi mất khi lưu.

    Nối bảng bằng query builder thay vì get_all trên bảng con, vì truy vấn bảng
    con mà không kèm doctype cha bị Frappe chặn.

    Hoá đơn trả hàng (`is_return`) không tính: trả hàng thì coi như chưa dùng mã.
    """
    if not customer or not coupon_code:
        return False

    sales_invoice = frappe.qb.DocType("Sales Invoice")
    coupon_applied = frappe.qb.DocType("POS Coupon Applied")

    rows = (
        frappe.qb.from_(coupon_applied)
        .join(sales_invoice)
        .on(coupon_applied.parent == sales_invoice.name)
        .select(sales_invoice.name)
        .where(
            (coupon_applied.coupon_code == coupon_code)
            & (coupon_applied.parenttype == "Sales Invoice")
            & (sales_invoice.customer == customer)
            & (sales_invoice.docstatus == 1)
            & (sales_invoice.is_return == 0)
        )
        .limit(1)
    ).run()

    return bool(rows)


def check_coupon_code(coupon_code, customer=None, company=None):
    """Validate and return coupon details"""
    res = {"coupon": None}

    if not frappe.db.exists("POS Coupon", {"coupon_code": coupon_code.upper()}):
        res["msg"] = _("Sorry, this coupon code does not exist")
        return res

    coupon = frappe.get_doc("POS Coupon", {"coupon_code": coupon_code.upper()})

    # Check if coupon is disabled
    if coupon.disabled:
        res["msg"] = _("Sorry, this coupon has been disabled")
        return res

    # Check validity dates
    if coupon.valid_from:
        if coupon.valid_from > getdate(today()):
            res["msg"] = _("Sorry, this coupon code's validity has not started")
            return res

    if coupon.valid_upto:
        if coupon.valid_upto < getdate(today()):
            res["msg"] = _("Sorry, this coupon code has expired")
            return res

    # Check usage limits
    if coupon.used and coupon.maximum_use and coupon.used >= coupon.maximum_use:
        res["msg"] = _("Sorry, this coupon code has been fully redeemed")
        return res

    # Check company
    if company and coupon.company != company:
        res["msg"] = _("Sorry, this coupon is not valid for this company")
        return res

    # Check customer (for Gift Cards)
    if coupon.coupon_type == "Gift Card" and coupon.customer:
        if not customer or coupon.customer != customer:
            res["msg"] = _("Sorry, this gift card is assigned to a specific customer")
            return res

    # Check one-time use per customer
    if coupon.one_use and customer:
        if customer_has_used_coupon(customer, coupon.coupon_code):
            res["msg"] = _("Sorry, you have already used this coupon code")
            return res

    # All validations passed
    res["coupon"] = coupon
    res["valid"] = True

    return res


def apply_coupon_discount(coupon, cart_total, net_total=None):
    """Calculate discount amount based on coupon configuration"""
    from frappe.utils import flt

    # Determine the base amount for discount calculation
    base_amount = cart_total if coupon.apply_on == "Grand Total" else (net_total or cart_total)

    # Check minimum amount
    if coupon.min_amount and flt(base_amount) < flt(coupon.min_amount):
        return {
            "valid": False,
            "message": _("Minimum cart amount of {0} is required").format(frappe.format_value(coupon.min_amount, {"fieldtype": "Currency"})),
            "discount": 0
        }

    # Calculate discount
    discount = 0
    if coupon.discount_type == "Percentage":
        discount = flt(base_amount) * flt(coupon.discount_percentage) / 100
    elif coupon.discount_type == "Amount":
        discount = flt(coupon.discount_amount)

    # Apply maximum discount limit
    if coupon.max_amount and flt(discount) > flt(coupon.max_amount):
        discount = flt(coupon.max_amount)

    # Ensure discount doesn't exceed cart total
    if discount > base_amount:
        discount = base_amount

    return {
        "valid": True,
        "discount": discount,
        "discount_type": coupon.discount_type,
        "discount_percentage": coupon.discount_percentage if coupon.discount_type == "Percentage" else None,
        "apply_on": coupon.apply_on
    }


def coupon_discount_on_totals(coupon, grand_total, total_taxes, precision=2):
    """Tiền giảm của mã trên một hoá đơn đã tính xong mọi giảm giá khác — cùng luật với
    `couponDiscount` của app POS native (`src/domain/cart/coupon.ts`).

    Gốc tính theo `apply_on` của mã, đúng nghĩa ERPNext:
    - "Grand Total" (mặc định): tổng cộng khách phải trả trước khi áp mã — sau giảm giá dòng, sau
      chiết khấu cả hoá đơn của khuyến mại, đã gồm thuế;
    - "Net Total": cũng số đó nhưng trước thuế.
    `min_amount` so với cùng số làm gốc; % hoặc số tiền, trần `max_amount`, không vượt chính gốc.

    Khác `apply_coupon_discount` ở trên (bản PWA còn dùng): bản đó tính "Grand Total" trên tiền hàng
    trước thuế, trước cả giảm giá dòng.

    Trả về dict:
    - amount: tổng cộng giảm đi (đã gồm thuế) — số khách bớt phải trả; 0 khi chưa đủ mức tối thiểu;
    - net_amount: phần trước thuế của amount;
    - missing: tổng cộng còn thiếu để tới mức tối thiểu; 0 là đã đủ.
    """
    gross = max(0.0, flt(grand_total))
    tax = min(max(0.0, flt(total_taxes)), gross)
    net = gross - tax
    on_net = coupon.apply_on == "Net Total"
    base = net if on_net else gross

    def to_gross(value):
        # Mã trước thuế giảm 100 thì tổng cộng giảm 100 × (tổng cộng / trước thuế).
        return value * gross / net if on_net and net > 0 else value

    min_amount = flt(coupon.min_amount)
    if min_amount > 0 and base < min_amount:
        return {"amount": 0, "net_amount": 0, "missing": flt(to_gross(min_amount - base), precision)}

    percentage = flt(coupon.discount_percentage) if coupon.discount_type == "Percentage" else 0
    fixed = flt(coupon.discount_amount) if coupon.discount_type == "Amount" else 0
    if percentage > 0:
        value = flt(base * percentage / 100, precision)
    elif fixed > 0:
        value = flt(fixed, precision)
    else:
        value = 0

    max_amount = flt(coupon.max_amount)
    if max_amount > 0 and value > max_amount:
        value = flt(max_amount, precision)
    value = max(0.0, min(value, base))
    if value <= 0:
        return {"amount": 0, "net_amount": 0, "missing": 0}

    # Giảm hết gốc thì giảm hết cả hai phần — không sót một đồng làm tròn.
    if value >= base:
        return {"amount": flt(gross, precision), "net_amount": flt(net, precision), "missing": 0}
    if on_net:
        return {"amount": flt(to_gross(value), precision), "net_amount": value, "missing": 0}
    return {
        "amount": value,
        "net_amount": flt(value * net / gross if gross > 0 else 0, precision),
        "missing": 0,
    }


def increment_coupon_usage(coupon_code):
    """Increment the usage counter for a coupon"""
    try:
        coupon = frappe.get_doc("POS Coupon", {"coupon_code": coupon_code.upper()})
        coupon.used = (coupon.used or 0) + 1
        coupon.db_set('used', coupon.used)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            title="Coupon Usage Increment Failed",
            message=f"Failed to increment usage for coupon {coupon_code}: {str(e)}"
        )


def decrement_coupon_usage(coupon_code):
    """Decrement the usage counter for a coupon (for cancelled invoices)"""
    try:
        coupon = frappe.get_doc("POS Coupon", {"coupon_code": coupon_code.upper()})
        if coupon.used and coupon.used > 0:
            coupon.used = coupon.used - 1
            coupon.db_set('used', coupon.used)
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            title="Coupon Usage Decrement Failed",
            message=f"Failed to decrement usage for coupon {coupon_code}: {str(e)}"
        )
