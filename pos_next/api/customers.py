"""
POS Next Customer API
Handles customer search, creation, and management for POS operations
"""

import re

import frappe
from frappe import _
from frappe.model.naming import getseries
from frappe.utils.nestedset import get_root_of


VN_COUNTRY_CODE = "84"


def default_territory():
    """Selling Settings' default, else the actual root Territory record.

    Do NOT hardcode "All Territories" - ERPNext's setup wizard names the
    root Territory in whatever language the site was installed in (e.g.
    "Tất cả khu vực" on a Vietnamese install), so that literal string
    doesn't exist as a real record on every site.
    """
    return frappe.db.get_single_value("Selling Settings", "territory") or get_root_of("Territory")


def default_customer_group():
    """Selling Settings' default, else the actual root Customer Group record.

    See default_territory() - "All Customer Groups" is likewise not a safe
    hardcoded literal.
    """
    return frappe.db.get_single_value("Selling Settings", "customer_group") or get_root_of("Customer Group")


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


def _shop_code_customer_code(pos_profile):
    """<Shop Code>+<sequence>, e.g. AP1, AP2 - one counter per POS Profile shop code.

    Uses frappe's Series counter (`tabSeries`, row-locked on read) so
    concurrent POS terminals never hand out the same number. Namespaced with
    a "CUSTCODE-" prefix on the counter key so it can't collide with an
    unrelated naming series that happens to use the same shop code text.
    """
    if not pos_profile:
        return None
    shop_code = frappe.db.get_value("POS Profile", pos_profile, "custom_shop_code")
    if not shop_code:
        return None
    seq = getseries(f"CUSTCODE-{shop_code}", 1)
    return f"{shop_code}{seq}"


def _get_unique_customer_code(customer_name, mobile_no=None, pos_profile=None):
    """
    Generate a unique customer_code when the field is mandatory.
    From POS: <shop_code><sequence>, e.g. AP1, AP2 (see _shop_code_customer_code).
    Otherwise prefers mobile_no: format 84 + digits (VN), e.g. 84862598791.
    Fallback: unique code from customer_name if no phone or phone invalid.
    """
    shop_code_result = _shop_code_customer_code(pos_profile)
    if shop_code_result:
        return shop_code_result

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
def create_customer(customer_name, mobile_no=None, email_id=None, customer_group=None, territory=None, company=None, pos_profile=None):
    """
    Create a new customer from POS.

    Args:
        customer_name (str): Customer name (required)
        mobile_no (str): Mobile number (optional)
        email_id (str): Email address (optional)
        customer_group (str): Customer group (default: Selling Settings' default / root Customer Group)
        territory (str): Territory (default: Selling Settings' default / root Territory)
        company (str): Company (optional, unused)
        pos_profile (str): POS Profile - used to derive the <shop_code><sequence> customer_code

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
        "customer_group": customer_group or default_customer_group(),
        "territory": territory or default_territory(),
        "mobile_no": mobile_no or "",
        "email_id": email_id or "",
    }

    # Set customer_code if the custom field exists and is mandatory (e.g. MBWNext Advanced Selling)
    if frappe.get_meta("Customer").has_field("customer_code"):
        doc_dict["customer_code"] = _get_unique_customer_code(
            customer_name, mobile_no=mobile_no, pos_profile=pos_profile
        )

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


def set_default_territory_and_customer_group(doc, method=None):
    """Before_insert hook: fill territory/customer_group when left blank.

    Covers CreateCustomerDialog.vue's direct frappe.client.insert call (no
    pos_next endpoint in between to default these server-side otherwise).
    """
    if not doc.get("territory"):
        doc.territory = default_territory()
    if not doc.get("customer_group"):
        doc.customer_group = default_customer_group()


def set_customer_code_if_mandatory(doc, method=None):
    """
    Before_insert hook: set customer_code when the custom field exists and is mandatory
    and the value is empty. From POS: <shop_code><sequence> (e.g. AP1, AP2 - see
    _shop_code_customer_code); else mobile_no + mã vùng VN (84), e.g. 84862598791;
    else fallback from customer_name.

    pos_profile comes from doc.flags.pos_profile (set by callers that construct
    the doc in Python, e.g. invoices.py's auto-create-customer fallback) or from
    doc.get("pos_profile") (a plain extra key in the insert payload - how
    CreateCustomerDialog.vue passes it through frappe.client.insert).
    """
    if not frappe.get_meta("Customer").has_field("customer_code"):
        return
    if doc.get("customer_code"):
        return
    doc.customer_code = _get_unique_customer_code(
        doc.customer_name or "CUST",
        mobile_no=doc.get("mobile_no"),
        pos_profile=doc.flags.get("pos_profile") or doc.get("pos_profile"),
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
