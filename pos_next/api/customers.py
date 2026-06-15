"""
POS Next Customer API
Handles customer search, creation, and management for POS operations
"""

import re

import frappe
from frappe import _


VN_COUNTRY_CODE = "84"


def _phone_to_vn_customer_code(mobile_no):
    """
    Convert phone number to Vietnam-style customer_code: 84 + digits (e.g. 84862598791).
    Strips non-digits, removes leading 0, prefixes 84 if not present.
    """
    if not mobile_no:
        return None
    digits = re.sub(r"\D", "", str(mobile_no).strip())
    if not digits:
        return None
    if digits.startswith(VN_COUNTRY_CODE):
        return digits
    if digits.startswith("0"):
        digits = digits[1:]
    return VN_COUNTRY_CODE + digits


def _get_unique_customer_code(customer_name, mobile_no=None):
    """
    Generate a unique customer_code when the field is mandatory.
    Prefers mobile_no: format 84 + digits (VN), e.g. 84862598791.
    Fallback: unique code from customer_name if no phone or phone invalid.
    """
    code = _phone_to_vn_customer_code(mobile_no) if mobile_no else None
    if code:
        candidate = code
        suffix = 0
        while frappe.db.exists("Customer", {"customer_code": candidate}):
            suffix += 1
            candidate = f"{code}-{suffix}"
        return candidate

    base = (customer_name or "").strip()
    base = re.sub(r"[^a-zA-Z0-9\u00C0-\u024F\s-]", "", base)
    base = re.sub(r"[-\s]+", "-", base).strip("-") or "CUST"
    base = base[:50]
    candidate = base
    suffix = 0
    while frappe.db.exists("Customer", {"customer_code": candidate}):
        suffix += 1
        candidate = f"{base}-{suffix}" if suffix <= 9999 else f"{base}-{frappe.generate_hash(length=6)}"
    return candidate


@frappe.whitelist()
def get_customers(search_term="", pos_profile=None, limit=20):

    """
    Search customers for inline customer selection in POS.

    Args:
        search_term (str): Search query (name, mobile, or customer ID)
        pos_profile (str): POS Profile to filter by customer group
        limit (int): Maximum number of results to return

    Returns:
        list: List of customer dictionaries with name, customer_name, mobile_no, email_id
    """
    try:
        frappe.logger().debug(
            f"get_customers called with search_term={search_term}, pos_profile={pos_profile}, limit={limit}"
        )

        filters = {}

        # Filter by POS Profile customer group if specified
        if pos_profile:
            frappe.logger().debug(f"Loading POS Profile: {pos_profile}")
            profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
            # Check if customer_group field exists (it may not exist in all versions)
            if hasattr(profile_doc, "customer_group") and profile_doc.customer_group:
                filters["customer_group"] = profile_doc.customer_group
                frappe.logger().debug(f"Filtering by customer_group: {profile_doc.customer_group}")

        # Return all customers (for client-side filtering)
        filters["disabled"] = 0
        customer_limit = limit if limit not in (None, 0) else frappe.db.count("Customer", filters)
        result = frappe.get_all(
            "Customer",
            filters=filters,
            fields=["name", "customer_name", "mobile_no", "email_id"],
            limit=customer_limit,
            order_by="customer_name asc",
        )
        frappe.logger().debug(f"get_customers returned {len(result)} customers")
        return result
    except Exception as e:
        frappe.logger().error(f"Error in get_customers: {str(e)}")
        frappe.logger().error(frappe.get_traceback())
        frappe.throw(_("Error fetching customers: {0}").format(str(e)))


@frappe.whitelist()
def create_customer(customer_name, mobile_no=None, email_id=None, customer_group="Individual", territory="All Territories", company=None):
    """
    Create a new customer from POS.

    Args:
        customer_name (str): Customer name (required)
        mobile_no (str): Mobile number (optional)
        email_id (str): Email address (optional)
        customer_group (str): Customer group (default: Individual)
        territory (str): Territory (default: All Territories)
        company (str): Company (optional, unused)

    Returns:
        dict: Created customer document
    """
    # Check if user has permission to create customers
    if not frappe.has_permission("Customer", "create"):
        frappe.throw(_("You don't have permission to create customers"), frappe.PermissionError)

    if not customer_name:
        frappe.throw(_("Customer name is required"))

    doc_dict = {
        "doctype": "Customer",
        "customer_name": customer_name,
        "customer_type": "Individual",
        "customer_group": customer_group or "Individual",
        "territory": territory or "All Territories",
        "mobile_no": mobile_no or "",
        "email_id": email_id or "",
    }

    # Set customer_code if the custom field exists and is mandatory (e.g. MBWNext Advanced Selling)
    if frappe.get_meta("Customer").has_field("customer_code"):
        doc_dict["customer_code"] = _get_unique_customer_code(customer_name, mobile_no=mobile_no)

    customer = frappe.get_doc(doc_dict)

    customer.insert()

    return customer.as_dict()


def auto_assign_loyalty_program(doc, method=None):
    """
    Auto-assign loyalty program to newly created customers.
    Called as after_insert hook on Customer doctype.

    Matches the customer against Loyalty Programs with auto_opt_in enabled,
    respecting each program's Customer Group / Customer Territory restrictions
    (same matching rules as erpnext.selling.doctype.customer.customer.set_loyalty_program).

    Args:
        doc: Customer document
        method: Hook method name (not used)
    """
    # Skip if customer already has a loyalty program
    if doc.loyalty_program:
        return

    from erpnext.selling.doctype.customer.customer import get_loyalty_programs

    loyalty_programs = get_loyalty_programs(doc)

    if len(loyalty_programs) == 1:
        # Use db_set to avoid triggering validate hooks again
        doc.db_set("loyalty_program", loyalty_programs[0], update_modified=False)
        frappe.logger().info(
            f"Auto-assigned loyalty program '{loyalty_programs[0]}' to customer '{doc.name}'"
        )


def set_customer_code_if_mandatory(doc, method=None):
    """
    Before_insert hook: set customer_code when the custom field exists and is mandatory
    and the value is empty. Uses mobile_no + mã vùng VN (84), e.g. 84862598791; else fallback from customer_name.
    """
    if not frappe.get_meta("Customer").has_field("customer_code"):
        return
    if doc.get("customer_code"):
        return
    doc.customer_code = _get_unique_customer_code(
        doc.customer_name or "CUST",
        mobile_no=doc.get("mobile_no"),
    )


@frappe.whitelist()
def get_customer_details(customer):
    """
    Get detailed customer information.

    Args:
        customer (str): Customer ID

    Returns:
        dict: Customer details
    """
    if not customer:
        frappe.throw(_("Customer is required"))

    return frappe.get_cached_doc("Customer", customer).as_dict()
