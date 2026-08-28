"""
POS Next Customer API
Handles customer search, creation, and management for POS operations
"""

import re

import frappe
from frappe import _
from frappe.utils import now_datetime
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
    """<Shop Code><YYMMDDHHMMSS>, e.g. AP260723083303 - shop code + the
    creation timestamp (second resolution), no running sequence number.
    """
    if not pos_profile:
        return None
    shop_code = frappe.db.get_value("POS Profile", pos_profile, "custom_shop_code")
    if not shop_code:
        return None
    timestamp = now_datetime().strftime("%y%m%d%H%M%S")
    candidate = f"{shop_code}{timestamp}"
    suffix = 0
    while frappe.db.exists("Customer", {"customer_code": candidate}):
        suffix += 1
        candidate = f"{shop_code}{timestamp}-{suffix}"
    return candidate


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


def _mobile_search_variants(search_term):
	"""Build mobile LIKE patterns for VN-style numbers (0904 ↔ 84-904 ↔ +84-904)."""
	digits = re.sub(r"\D", "", search_term or "")
	patterns = set()
	if not digits:
		return patterns

	patterns.add(f"%{digits}%")
	if digits.startswith("0") and len(digits) > 1:
		rest = digits[1:]
		patterns.add(f"%{rest}%")
		patterns.add(f"%{VN_COUNTRY_CODE}{rest}%")
	elif digits.startswith(VN_COUNTRY_CODE) and len(digits) > len(VN_COUNTRY_CODE):
		rest = digits[len(VN_COUNTRY_CODE) :]
		patterns.add(f"%0{rest}%")
		patterns.add(f"%{rest}%")

	return patterns


@frappe.whitelist()
def get_customers(search_term="", pos_profile=None, limit=20):
	"""
	Search customers for inline customer selection in POS.

	Args:
		search_term (str): Search query (name, mobile, or customer ID)
		pos_profile (str): POS Profile to filter by customer group
		limit (int): Max results. 0 + empty search_term = full list (offline cache).

	Returns:
		list: Customer dicts with name, customer_name, mobile_no, email_id
	"""
	try:
		from frappe.utils import cint

		search_term = (search_term or "").strip()
		limit = cint(limit)

		filters = {"disabled": 0}

		if pos_profile:
			profile_doc = frappe.get_cached_doc("POS Profile", pos_profile)
			if hasattr(profile_doc, "customer_group") and profile_doc.customer_group:
				filters["customer_group"] = profile_doc.customer_group

		# customer_group and territory are needed to decide whether an offer limited
		# via applicable_for covers this customer (PM-TASK-00034).
		fields = [
			"name",
			"customer_name",
			"mobile_no",
			"email_id",
			"customer_group",
			"territory",
		]

		def _fill_scope_defaults(rows):
			"""Mirror the fallback apply_offers() uses, so the POS judges offers
			limited by customer group / territory the same way the server will.
			Plenty of imported customers have both fields blank."""
			fallback_group = None
			fallback_territory = None
			for row in rows:
				if not row.get("customer_group"):
					if fallback_group is None:
						fallback_group = default_customer_group()
					row["customer_group"] = fallback_group
				if not row.get("territory"):
					if fallback_territory is None:
						fallback_territory = default_territory()
					row["territory"] = fallback_territory
			return rows

		# Empty search: used for offline full dump when limit=0
		if not search_term:
			customer_limit = limit if limit > 0 else frappe.db.count("Customer", filters)
			return _fill_scope_defaults(
				frappe.get_all(
					"Customer",
					filters=filters,
					fields=fields,
					limit=customer_limit,
					order_by="customer_name asc",
				)
			)

		# Search mode — always capped (never return unbounded results)
		max_results = limit if limit > 0 else 20
		or_filters = [
			["customer_name", "like", f"%{search_term}%"],
			["name", "like", f"%{search_term}%"],
			["mobile_no", "like", f"%{search_term}%"],
		]
		for pattern in _mobile_search_variants(search_term):
			or_filters.append(["mobile_no", "like", pattern])

		result = frappe.get_all(
			"Customer",
			filters=filters,
			or_filters=or_filters,
			fields=fields,
			limit=max_results,
			order_by="customer_name asc",
		)
		return _fill_scope_defaults(result)
	except Exception as e:
		frappe.logger().error(f"Error in get_customers: {str(e)}")
		frappe.logger().error(frappe.get_traceback())
		frappe.throw(_("Error fetching customers: {0}").format(str(e)))


@frappe.whitelist()
def get_customer_scope(customer):
	"""Current customer group / territory of one customer, defaults filled in.

	The POS keeps whole customer objects in its recent/frequent lists, in the
	offline cache and in the saved cart, so the group on a selected customer can
	be hours old. Deciding whether a customer-scoped promotion applies from that
	stale copy hides promotions the customer really qualifies for, so the cart
	re-reads the scope here whenever the customer changes (PM-TASK-00033).
	"""
	if not customer:
		return {}

	# get_customers() above reads through frappe.get_all(), which applies
	# permissions; a raw get_value() here would be a looser door onto the same
	# data, so check explicitly.
	if not frappe.has_permission("Customer", "read", doc=customer):
		frappe.throw(_("Not permitted to read this customer"), frappe.PermissionError)

	row = frappe.db.get_value(
		"Customer", customer, ["name", "customer_group", "territory"], as_dict=True
	)
	if not row:
		return {}

	return {
		"name": row.name,
		"customer_group": row.customer_group or default_customer_group(),
		"territory": row.territory or default_territory(),
	}


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
