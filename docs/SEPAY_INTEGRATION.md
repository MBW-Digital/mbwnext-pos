# Tích hợp SePay vào POS Next

Tài liệu hướng dẫn cấu hình và sử dụng cổng thanh toán SePay (VietQR) trong POS Next.

## Tổng quan

SePay cho phép khách hàng thanh toán qua chuyển khoản ngân hàng bằng cách quét mã QR. Khi khách chuyển tiền, SePay gửi webhook đến hệ thống và tự động xác nhận thanh toán.

## Cấu hình

### 1. Cấu hình POS Settings

1. Vào **POS Settings** (liên kết với POS Profile của bạn)
2. Bật **Enable SePay Bank Transfer**
3. Điền thông tin:
   - **Bank Account Number**: Số tài khoản ngân hàng nhận tiền
   - **Bank Code**: Mã ngân hàng (vd: `MBBank`, `Vietcombank`). [Danh sách mã ngân hàng](https://qr.sepay.vn)
   - **Account Holder Name**: Tên chủ tài khoản

### 2. Cấu hình Webhook tại SePay

1. Đăng nhập [my.sepay.vn](https://my.sepay.vn)
2. Vào **WebHooks** → **Thêm webhooks**
3. Cấu hình:
   - **Đặt tên**: VD "POS Next"
   - **Sự kiện**: Chọn "Có tiền vào"
   - **Khi tài khoản ngân hàng là**: Chọn tài khoản đã liên kết
   - **Gọi đến URL**: `https://YOUR_DOMAIN/api/method/pos_next.api.sepay.receive_webhook`
   - **Request Content Type**: `application/json`
   - **Chứng thực**: Không chứng thực (hoặc API Key nếu cần bảo mật)

### 3. Cấu hình mã thanh toán tại SePay

1. Vào **Công ty** → **Cấu hình chung** → **Cấu trúc mã thanh toán**
2. Đảm bảo cấu trúc nhận diện mã `DH` + số (vd: `DH123` cho đơn hàng 123)

## Luồng thanh toán

1. Khách chọn sản phẩm, nhấn **Thanh toán**
2. Có thể thanh toán hỗn hợp: thêm tiền mặt (hoặc phương thức khác) trước, phần còn lại chọn **Bank Draft** → **Pay via Bank Transfer**
3. Nhấn **Pay via Bank Transfer** (hiển thị số tiền còn lại cần chuyển)
4. Hệ thống tạo hóa đơn nháp (đã ghi nhận các khoản thanh toán trước) và hiển thị mã QR với số tiền còn lại
5. Khách quét QR bằng app ngân hàng và chuyển đúng số tiền hiển thị
6. SePay nhận giao dịch → gửi webhook → hệ thống tự động submit hóa đơn và ghi nhận thanh toán chuyển khoản
7. Giao diện polling phát hiện thanh toán → hiển thị thành công

## API Endpoints

| Endpoint | Mô tả |
|----------|-------|
| `pos_next.api.sepay.get_vietqr_url` | Lấy URL ảnh VietQR cho thanh toán |
| `pos_next.api.sepay.check_sepay_payment_status` | Kiểm tra trạng thái thanh toán (polling) |
| `pos_next.api.sepay.receive_webhook` | Webhook nhận thông báo từ SePay (allow_guest) |

## Lưu ý

- **Thanh toán hỗn hợp**: Đơn 5000 VND có thể chia 3000 tiền mặt + 2000 chuyển khoản. Thêm tiền mặt trước, chọn Bank Draft, nhấn "Pay via Bank Transfer" — QR sẽ hiển thị 2000 VND.
- **Mã đơn hàng**: Nội dung chuyển khoản phải chứa `DH` + số (vd: `DH1` cho SINV-00001)
- **Chống trùng**: Webhook xử lý deduplication bằng `sepay_id` và kiểm tra invoice đã submit
- **Môi trường test**: Dùng [my.dev.sepay.vn](https://my.dev.sepay.vn) để giả lập giao dịch
- **Chạy trên localhost**: SePay không thể gửi webhook đến 127.0.0.1. Sau khi khách chuyển khoản, nhấn **"I have received the transfer - Confirm manually"** để xác nhận thủ công.

## Tài liệu tham khảo

- [Tích hợp Webhook SePay](https://developer.sepay.vn/vi/sepay-webhooks/tich-hop-webhook)
- [Lập trình cổng thanh toán](https://sepay.vn/lap-trinh-cong-thanh-toan.html)
- [Kết nối MB Bank API](https://docs.sepay.vn/ket-noi-mb-api.html)
