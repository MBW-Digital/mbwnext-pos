# -*- coding: utf-8 -*-
"""Cấp token đăng nhập cho app POS chạy native (React Native).

App native không có trang HTML boot của Frappe nên không dùng được cookie session + CSRF như
bản PWA. Thay vào đó: đăng nhập một lần bằng usr/pwd, nhận `api_key` và `api_secret`, lưu vào
`expo-secure-store`, rồi mọi request sau gắn header

	Authorization: token <api_key>:<api_secret>

Frappe **đã nhận sẵn** header này (`frappe/auth.py`, `validate_auth_via_api_keys`) nên tầng xác
thực không phải làm gì thêm. Cái thiếu là đường CẤP token: `generate_keys` của Frappe
(`frappe/core/doctype/user/user.py`) gọi `frappe.only_for("System Manager")`, mà thu ngân không
có role đó nên không tự lấy được token — vì vậy mới cần endpoint riêng ở đây.

Tham chiếu: `docs/pwa-to-rn-analysis.md` trong repo `pos-next-mobile`, câu Q4.

So với `mbwnext_superapp.api.superapp.issue_token` (bản dựng trước cho SuperApp), bản này thêm
bốn lớp chặn mà bản kia thiếu:

1. `methods=["POST"]` — không cho GET, để mật khẩu không nằm trong query string rồi trôi vào
   access log của nginx, log proxy và history.
2. `@rate_limit` — chặn dò mật khẩu. Bản SuperApp mở guest mà không có hạn mức nào.
3. Kiểm `User.enabled` — `check_password` của Frappe **chỉ so hash trong `__Auth`**, không xét
   user đã bị vô hiệu hoá, nên thiếu bước này thì tài khoản đã tắt vẫn lấy được token.
4. Kiểm quyền vào POS — chỉ cấp cho user được gán POS Profile, không cấp cho mọi User của site.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

# Hạn mức tính theo cặp (IP, usr) — mặc định `ip_based=True` của `rate_limit`.
#
# Chọn có `usr` trong khoá để một thu ngân gõ sai mật khẩu nhiều lần chỉ khoá tài khoản đó ở
# quầy đó, không khoá các quầy khác của cùng cửa hàng: mọi quầy thường đi ra internet bằng
# một IP, khoá theo IP trần là khoá cả cửa hàng giữa giờ bán.
#
# `rate_limit` đếm CẢ request thành công (xem `frappe/rate_limiter.py`: nó incr trước khi gọi
# hàm), nên hạn mức phải đủ rộng cho việc mở app hàng ngày ở nhiều quầy, chỉ cần chặn dò mật
# khẩu là đủ.
TOKEN_RATE_LIMIT = 10
TOKEN_RATE_WINDOW = 5 * 60


def _sai_dang_nhap():
	"""Một câu lỗi duy nhất cho mọi trường hợp sai ở bước xác thực.

	Không phân biệt "không có user" với "sai mật khẩu": phân biệt là cho người ngoài biết tài
	khoản nào có thật trên site.
	"""
	frappe.throw(_("Incorrect username or password."), frappe.AuthenticationError)


def _lay_hoac_tao_token(user_doc) -> tuple[str, str]:
	"""`api_key` + `api_secret` của user. Tạo mới nếu chưa có, GIỮ NGUYÊN nếu đã có.

	Frappe chỉ cho **một** cặp key/secret trên mỗi User, nên đây là token dùng chung cho mọi
	thiết bị của user đó, không phải token theo từng máy.

	Cố ý giữ secret cũ thay vì cấp lại mỗi lần đăng nhập: một cửa hàng có thể mở app trên nhiều
	quầy bằng cùng một tài khoản, cấp lại secret sẽ đá các quầy kia ra giữa ca — mất giao dịch
	đang dở, đúng lúc đông khách.

	Đánh đổi phải biết: **không thu hồi được riêng một máy**. Mất máy thì xoá `api_key` của user
	đó (mọi máy phải đăng nhập lại). Muốn thu hồi theo từng máy thì phải chuyển sang OAuth2 hoặc
	tự làm doctype token theo thiết bị — không nằm trong phạm vi bản này.
	"""
	if user_doc.api_key:
		try:
			api_secret = user_doc.get_password("api_secret") or ""
		except Exception:
			# Không giải mã được secret: encryption key của site đã đổi sau khi restore hoặc
			# migrate. Không cứu được bản cũ, cấp lại bản mới bên dưới.
			api_secret = ""

		if api_secret:
			return user_doc.api_key, api_secret

	api_key = user_doc.api_key or frappe.generate_hash(length=15)
	api_secret = frappe.generate_hash(length=15)

	user_doc.api_key = api_key
	user_doc.api_secret = api_secret
	user_doc.save(ignore_permissions=True)
	# Commit ngay: đây là request của Guest, chốt luôn cho chắc thay vì đợi cuối request.
	frappe.db.commit()

	return api_key, api_secret


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="usr", limit=TOKEN_RATE_LIMIT, seconds=TOKEN_RATE_WINDOW)
def issue_token(usr: str, pwd: str) -> dict:
	"""Đổi usr/pwd lấy token dùng cho app POS native.

	Gọi:

		POST /api/method/pos_next.api.auth.issue_token
		{"usr": "thungan@cuahang.vn", "pwd": "..."}

	Trả về:

		{
			"api_key": "...",
			"api_secret": "...",
			"user": "thungan@cuahang.vn",
			"full_name": "Nguyễn Thu Ngân",
			"pos_profiles": [{"name": ..., "company": ..., "warehouse": ..., ...}]
		}

	`pos_profiles` trả kèm luôn vì bước kiểm quyền bên dưới đã phải truy vấn danh sách này —
	app đỡ một lượt gọi nữa trước khi mở màn chọn ca.

	App lưu `api_key`/`api_secret` vào `expo-secure-store`, KHÔNG lưu mật khẩu. Token không có
	hạn dùng: gặp 401 thì bắt đăng nhập lại, không có luồng refresh.
	"""
	from frappe.utils.password import check_password

	from pos_next.api.pos_profile import get_accessible_pos_profiles_for_user

	if not usr or not pwd:
		_sai_dang_nhap()

	# Xác thực mật khẩu TRƯỚC mọi kiểm tra khác. Đảo thứ tự (ví dụ kiểm `enabled` trước) là cho
	# người ngoài dò được tài khoản nào tồn tại mà chưa cần mật khẩu đúng.
	try:
		user_name = check_password(usr.strip(), pwd)
	except frappe.AuthenticationError:
		_sai_dang_nhap()

	user_doc = frappe.get_doc("User", user_name)

	# `check_password` chỉ so hash trong `__Auth`, không xét `enabled`. Thiếu bước này thì tài
	# khoản đã cho nghỉ việc vẫn lấy được token và bán hàng bình thường.
	if not user_doc.enabled:
		frappe.throw(_("This account has been disabled."), frappe.AuthenticationError)

	# Từ đây mật khẩu đã đúng, nên nói rõ lý do được: không còn là kênh dò tài khoản, và thu
	# ngân cần biết phải nhờ ai gán POS Profile.
	pos_profiles = get_accessible_pos_profiles_for_user(user_doc.name)
	if not pos_profiles:
		frappe.throw(
			_("This account has no POS Profile assigned. Contact your administrator for access to sell."),
			frappe.PermissionError,
		)

	api_key, api_secret = _lay_hoac_tao_token(user_doc)

	# Ghi lại việc cấp token: cần cho việc lần lại khi mất máy hoặc nghi bị dùng trái phép.
	frappe.logger("pos_next_auth", allow_site=True).info(
		f"issue_token: cấp token cho {user_doc.name} từ IP {frappe.local.request_ip}"
	)

	return {
		"api_key": api_key,
		"api_secret": api_secret,
		"user": user_doc.name,
		"full_name": user_doc.full_name or "",
		"pos_profiles": pos_profiles,
	}
