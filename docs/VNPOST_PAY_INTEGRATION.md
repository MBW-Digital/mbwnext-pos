# Tích hợp VNPost Pay (Open Hub / VNPD) — POS Next

Tài liệu tham chiếu: `apps/pos_next/VNPost_Pay.pdf` (Open Hub API).

## Cấu hình POS Profile

1. **Payment gateway**: chọn `VNPost Pay`
2. Bật **Enable VNPost Pay (Bank Transfer)**
3. **Bank / Account (tuỳ chọn)**: hiển thị trên in nhiệt nếu API không trả đủ
4. Điền nhóm trường **VNPost API** (base URL, user, password, `serviceCode`, `partnerCode`, `partnerAccNo`, `POCode`, private key RSA PEM, public key VNPD để verify callback)

## Callback

Đăng ký tại VNPD URL công khai (HTTPS), ví dụ:

`https://YOUR_DOMAIN/api/method/pos_next.api.vnpost_pay.receive_callback`

Cấu hình chữ ký: lưu **public key** VNPD trường `vnpost_vnpd_public_key` trên POS Profile. Trên môi trường dev (developer_mode) có thể bỏ qua verify tạm thời nếu chưa có key.

## API nội bộ (whitelist)

| Method | Mô tả |
|--------|--------|
| `pos_next.api.vnpost_pay.get_vietqr_url` | Tạo/lấy dữ liệu thanh toán (tên giữ tương thích; thực chất gọi VNPost API) |
| `pos_next.api.vnpost_pay.get_vnpost_payment_qr_data` | Tương tự, tên rõ ràng |
| `pos_next.api.vnpost_pay.check_vnpost_payment_status` | Polling trạng thái hóa đơn |
| `pos_next.api.vnpost_pay.manual_confirm_vnpost_payment` | Xác nhận thủ công (localhost / sự cố callback) |
| `pos_next.api.vnpost_pay.receive_callback` | Callback VNPD → `allow_guest` |

## Lưu ý

- Cần thư viện Python `cryptography` (RSA–SHA256).
- Một số phản hồi VNPost chỉ có `baseUrl`/`socketUrl` cho SDK: POS hiển thị hướng dẫn; khi cần bổ sung tích hợp web SDK theo tài liệu riêng VNPD.
