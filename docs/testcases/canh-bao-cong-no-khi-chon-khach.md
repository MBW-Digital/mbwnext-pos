# Test case — Cảnh báo công nợ khi chọn khách (PM-FEAT-00068)

Tài liệu tính năng: [`docs/features/canh-bao-cong-no-khi-chon-khach.md`](../features/canh-bao-cong-no-khi-chon-khach.md)

Vòng 1: Claude chạy ngày 02/10/2026 trên site dev, cột "Kết quả thực tế" ghi đúng kết quả lần chạy đó và cách kiểm.
Vòng 2 / 2b: Claude Pos Next 2 rà chéo, ghi ở cuối file.
Vòng 3 (người kiểm, từ 03/10/2026): làm theo mục **Danh sách test tay** ngay dưới, ghi kết quả vào cột "Người kiểm" của từng mã.

## Điều kiện chuẩn bị

| Mục | Giá trị |
|---|---|
| Site | `pos.next` — http://localhost:8003/pos (web server 8003) |
| Tài khoản | `tratthunguyen1215@gmail.com` (Trà) — thuộc quầy POS Chiềng Sại, có quyền xem / thu / hoàn tiền thu nợ |
| Quầy | POS Chiềng Sại (company Chi Nhánh Sơn La, số ngày được nợ 7), ca đang mở POSA-OS-26-0000027 |
| Cách vào tính năng (bán hàng) | Đăng nhập → mở **POS** (`/pos`) → chọn quầy POS Chiềng Sại, mở ca → ô **Tìm hoặc thêm khách** bên phải → gõ tên / SĐT → bấm vào khách |
| Cách vào cấu hình | Desk → **POS Profile** → POS Chiềng Sại → khối dưới "Số ngày được nợ": **Bật cảnh báo công nợ**, **Ngưỡng tổng nợ tối thiểu**, **Nhóm khách không cảnh báo** → Lưu → trên POS bấm biểu tượng đồng bộ (hoặc tải lại trang) |

**Dữ liệu dùng** (hiện trạng sau lần thu nợ thật của chức năng 1 lúc 14:37 ngày 02/10/2026):

| Khách | Mã | Nợ tại POS Chiềng Sại |
|---|---|---|
| 0975961375 | `840975961375-1` (nhóm Individual) | 154.900,01 — ACC-SINV-2026-00101 154.900 **quá hạn** (hạn 01/08) + ACC-SINV-2026-00061 0,01 **đã trả một phần** |
| a chinh | `KH003779` | có nợ (dùng cho ca đổi nhanh khách) |
| 335008602 | `335008602` | không nợ |
| 840975961375 | `840975961375` | 934.000 ở company **Chi Nhánh Hà Đông**, không nợ ở Sơn La |

Cấu hình quầy khi chạy: Bật cảnh báo = 1, Ngưỡng = 0, Nhóm loại trừ = trống, Cho phép bán chịu = theo POS Settings.

Từ 02/10/2026 pos.next tắt cho phép tồn âm và bật giữ tồn (Stock Settings, để thử chức năng Giữ hàng): ca nào cần bán thật (TC-REGR-01) phải chọn hàng còn tồn.

Ký hiệu cách kiểm: **UI** = bấm trên màn hình POS bằng Chrome · **JS** = đặt trạng thái bằng console trình duyệt rồi quan sát màn hình · **API** = gọi hàm máy chủ bằng `bench console` dưới đúng user.

## Danh sách test tay (vòng người kiểm)

Trước khi test: bench 8003 đã khởi động lại sau bản sửa 03/10 và bundle POS đã build lại. Trên Chrome, mở DevTools → Application → **Service Workers → Unregister** và **Storage → Clear site data**, rồi tải lại `/pos`.

Đây là các ca Claude **không tự chạy được** (cần thu tiền thật, đăng nhập lại, user thật, hoặc thanh toán thật). Các ca còn lại đã Pass, người kiểm chỉ cần xem lại nếu muốn.

| # | Mã | Việc cần làm | Lưu ý |
|---|---|---|---|
| 1 | TC-HAPPY-01…07 | Chọn khách `0975961375` → xem hộp cảnh báo, bấm Tiếp tục bán / huy hiệu Nợ / Đổi khách | Đọc lại cho quen màn hình; Claude đã Pass |
| 2 | TC-HAPPY-09 | Thu nợ ngay → **thu một phần thật** → Đóng | Tạo Payment Entry thật; huỷ (cancel) sau khi xong nếu không muốn giữ |
| 3 | TC-HAPPY-10 | Thu nợ ngay → **thu hết** thật → Đóng | Cảnh báo không mở lại, huy hiệu biến mất |
| 4 | TC-PERM-05 / 11 | Đăng nhập bằng một user thuộc quầy nhưng **không** có vai trò thu nợ | Thấy cảnh báo, không có nút Thu nợ ngay |
| 5 | TC-PERM-12 | (a) Đăng xuất → đăng nhập lại → IndexedDB `pos_next_offline` → `customer_debts` phải trống trước khi nạp lại. (b) Đóng ca → bảng không còn dòng của quầy | Đóng ca thật — chỉ làm khi được phép đóng ca POSA-OS-26-0000027 |
| 6 | TC-EDGE-26 | Đổi POS Settings của quầy (Cho bán chịu / Cho trả một phần) → chọn khách nợ → xem dòng ghi chú trong hộp cảnh báo | Nhớ trả cấu hình về như cũ: Cho bán chịu = 1, Trả một phần = 0 |
| 7 | TC-EDGE-18 | Khai Hạn mức công nợ 100.000 (company Chi Nhánh Sơn La) cho khách `840975961375-1` → chọn khách | Xoá hạn mức sau khi test |
| 8 | TC-CFG-07 | Desk tiếng Việt → POS Profile → tab Thu nợ: đọc nhãn + mô tả 3 ô | — |
| 9 | TC-REGR-01 / 02 | Chọn khách có nợ → bán hàng, thanh toán đủ; khách có ưu đãi theo nhóm → ưu đãi vẫn áp | Chọn hàng còn tồn (site đã tắt tồn âm) |
| 10 | TC-REGR-05 | Có hoá đơn offline chưa đồng bộ → mở bản POS mới | Hoá đơn offline không mất, đồng bộ được |
| 11 | TC-HAPPY-12 / TC-EDGE-13 | Tắt mạng (DevTools → Network → Offline) → chọn khách nợ / khách chưa nạp | Dải xám "Đang mất mạng", nút Thu nợ mờ |

Không dùng khách **C HUỆ KH007434** và hàng 1000002260, 1000012648 (đang dành cho chức năng Giữ hàng).

## TC-HAPPY — Luồng chính

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-HAPPY-01 | Ở giỏ trống, gõ `0975961375` vào ô tìm khách, bấm vào khách | Hộp thoại **"Khách hàng đang còn nợ"** bật lên: tên, SĐT, "Tổng nợ tại quầy · 2 đơn", **154.900,01** | Pass | UI | |
| TC-HAPPY-02 | Xem bảng đơn trong hộp thoại | 2 dòng, cũ trước: 00061 (03/06, hạn 10/06, nhãn xanh **Đã trả một phần**, 0,01) rồi 00101 (25/07, hạn 01/08, nền đỏ, nhãn **Quá hạn 62 ngày**, 154.900,00). Cột "Số ngày" = số ngày từ ngày bán | Pass (số ngày quá hạn tính theo ngày chạy) | UI | |
| TC-HAPPY-03 | Xem ô hạn mức | "Hạn mức công nợ: Không giới hạn", "Đang nợ tại quầy: 154.900,01", "Còn được nợ: —" | Pass | UI | |
| TC-HAPPY-04 | Xem ghi chú vàng | "Khách có 1 đơn quá hạn. Nhắc khách trả nợ trước khi bán tiếp — cảnh báo chỉ để thông tin." | Pass | UI | |
| TC-HAPPY-05 | Bấm **Tiếp tục bán hàng** | Hộp thoại đóng, khách vẫn trên giỏ, cạnh tên có huy hiệu đỏ **"Nợ ₫154.900,01 · Quá hạn"** | Pass | UI | |
| TC-HAPPY-06 | Bấm vào huy hiệu Nợ | Hộp thoại cảnh báo mở lại, cùng số liệu | Pass | UI | |
| TC-HAPPY-07 | Bấm **Đổi khách hàng** | Hộp thoại đóng, khách bị bỏ khỏi giỏ, con trỏ nằm sẵn trong ô tìm khách | Pass | UI | |
| TC-HAPPY-08 | Chọn lại khách → bấm **Thu nợ ngay** | Cảnh báo đóng, hộp **Thu nợ khách hàng** mở với đúng khách, các đơn nợ đã được tick sẵn, số thu = tổng nợ | Pass | UI | |
| TC-HAPPY-09 | Trong hộp Thu nợ (từ TC-HAPPY-08) thu một phần, xem kết quả "Đã thu …" rồi bấm **Đóng** | Lúc còn màn kết quả, cảnh báo **chưa** bật đè lên. Sau khi bấm Đóng, cảnh báo mở lại với tổng nợ đã giảm; huy hiệu cập nhật số mới | Pass (tín hiệu "thu xong" giả lập, không tạo Payment Entry) | JS | |
| TC-HAPPY-10 | Như TC-HAPPY-09 nhưng thu **hết** nợ | Sau khi đóng hộp Thu nợ, cảnh báo không mở lại, huy hiệu Nợ biến mất | Pass phía máy chủ — Claude POS thu hết trong giao dịch rồi hoàn tác: API trả `show: false` (02/10/2026). Cần người test trên màn hình với lần thu thật | API | |
| TC-HAPPY-11 | Đổi cấu hình: Ngưỡng = 50.000 → chọn khách 0975961375 | Vẫn cảnh báo (154.900,01 ≥ 50.000) | Pass | API + UI (vòng trước) | |
| TC-HAPPY-12 | Mở POS ở chế độ online, chờ 5 giây, rồi tắt mạng (DevTools → Network → Offline) → chọn khách 0975961375 | Cảnh báo vẫn hiện, có dải xám "Đang mất mạng · Công nợ cập nhật lúc HH:mm dd/MM — có thể đã thay đổi"; không có ô hạn mức; nút **Thu nợ ngay** mờ, rê chuột hiện "Cần kết nối mạng để thu nợ"; huy hiệu màu xám kèm giờ | Pass (8 khách được nạp sẵn) | UI (vòng trước) | |

## TC-CFG — Cấu hình trên POS Profile (chạy 02/10/2026)

Cách vào: Desk → **POS Profile** → POS Chiềng Sại → tab **Thu nợ** (Debt Collection).

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-CFG-01 | Mở tab Thu nợ | Có 3 ô: **Bật cảnh báo công nợ**, **Ngưỡng tổng nợ tối thiểu**, **Nhóm khách không cảnh báo**, đứng liền nhau, mỗi ô có dòng mô tả | **Fail → đã sửa** — lần đầu thứ tự trong tab bị xáo (ô cảnh báo xen giữa các ô quyền, có 3 ô SePay lẫn vào), do fixture neo `sepay_bank_code` vào trường không tồn tại `vnpost_sdk_show_pttt` và tab Thu nợ neo vào `sepay_bank_code`. Chức năng 1 đã sửa neo và migrate. Kiểm lại: SePay về tab Chi tiết. **Cập nhật 03/10/2026** — anh Quân chốt thứ tự mới: "Bật cảnh báo công nợ" ở đầu tab, ngưỡng + nhóm loại trừ cuối cột phải dưới "Số ngày được nợ"; fixture đã đổi neo theo, kiểm trên pos.next đúng thứ tự | UI |  |
| TC-CFG-02 | Bỏ tick **Bật cảnh báo công nợ** | Ô Ngưỡng và ô Nhóm khách ẩn đi; tick lại thì hiện lại | Pass | UI | |
| TC-CFG-03 | Gõ "Indiv" vào ô **Nhóm khách không cảnh báo** | Danh sách gợi ý nhóm khách (Individual, HAMPER…), chọn được nhiều nhóm | Pass | UI | |
| TC-CFG-04 | Chọn **Individual** → Lưu → chọn khách 0975961375 trên POS | Lưu được; khách nhóm Individual không còn cảnh báo, cũng không có trong danh sách nạp sẵn cho chế độ mất mạng | Pass (nạp sẵn còn 6 khách, mất 2 khách nhóm Individual) | UI + API | |
| TC-CFG-05 | Chọn nhóm cha **Individual**, khách thuộc nhóm con **HAMPER** | Khách nhóm con cũng không cảnh báo | **Fail → đã sửa** — bản đầu chỉ so đúng tên nhóm. Sửa: loại cả nhóm con; mô tả ô ghi "kể cả nhóm con". Kiểm lại: danh sách loại trừ = {Individual, HAMPER}. Site chưa có khách nhóm HAMPER đang nợ để thử trên màn hình | API | |
| TC-CFG-06 | Nhập **-5000** vào ô Ngưỡng → Lưu | Chặn: "Value cannot be negative for POS Profile: Debt Warning Minimum Amount" | **Fail → đã sửa** — bản đầu cho lưu số âm. Đã đặt `non_negative`; kiểm lại: hiện hộp "Negative Value" với đúng câu trên, không lưu | UI | |
| TC-CFG-07 | Nhãn và mô tả 3 ô khi Desk dùng tiếng Việt | "Bật cảnh báo công nợ", "Ngưỡng tổng nợ tối thiểu", "Nhóm khách không cảnh báo" kèm mô tả tiếng Việt | Pass phần bản dịch (đủ trong vi.csv). Cần người test trên màn hình tiếng Việt | Đối chiếu file | |
| TC-CFG-08 | Đổi cấu hình rồi quay lại POS đang mở, bấm đồng bộ / tải lại | POS dùng cấu hình mới | Pass (vòng trước, với Ngưỡng 50.000) | UI | |

Sau khi chạy: nhóm loại trừ trả về trống, Bật cảnh báo = 1, Ngưỡng = 0. Nhóm khách Individual không bị sửa (lỡ mở trang nhóm khi bấm, đã kiểm `modified` vẫn là 13/05/2026).

## TC-VALID — Dữ liệu sai bị chặn đúng thông báo

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-VALID-01 | Gọi API không truyền quầy | Lỗi `POS Profile is required` (vi: "Cần chọn POS Profile") | Pass | API | |
| TC-VALID-02 | Gọi API với quầy không tồn tại `ZZ-POS-KHONG-CO` | Lỗi quyền `You are not assigned to POS Profile ZZ-POS-KHONG-CO` (kiểm user thuộc quầy chạy trước, nên quầy không tồn tại cũng báo như không thuộc quầy — không lộ quầy nào có thật) | Pass | API | |
| TC-VALID-03 | Ô **Ngưỡng tổng nợ tối thiểu** trên POS Profile | Là ô tiền tệ, chỉ hiện khi đã tick "Bật cảnh báo công nợ" | Pass | UI Desk (vòng trước) | |

Tính năng chỉ đọc, không có ô nhập trên POS, nên không có thêm ca chặn nhập liệu.

## TC-EDGE — Trường hợp biên

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-EDGE-01 | Chọn khách không nợ `335008602` | Không có hộp thoại, không có huy hiệu | Pass (`show: false`) | API | |
| TC-EDGE-02 | Chọn khách chỉ nợ ở company khác (`840975961375`, nợ 934.000 ở Chi Nhánh Hà Đông) | Không cảnh báo | Pass (`show: false`) | API | |
| TC-EDGE-03 | Tắt "Bật cảnh báo công nợ" trên quầy → chọn khách 0975961375 | Không hộp thoại, không huy hiệu | Pass | API (cấu hình giả lập) | |
| TC-EDGE-04 | Khách là **khách lẻ mặc định** của quầy | Không cảnh báo | Pass (giả lập — POS Chiềng Sại chưa đặt khách mặc định) | API | |
| TC-EDGE-05 | Thêm nhóm **Individual** vào "Nhóm khách không cảnh báo" → chọn khách 0975961375 | Không cảnh báo | Pass | API + UI (vòng trước) | |
| TC-EDGE-06 | Ngưỡng = 300.000 (lớn hơn tổng nợ) | Không cảnh báo | Pass | API | |
| TC-EDGE-07 | Ngưỡng = đúng tổng nợ 154.900,01 | **Có** cảnh báo (so ≥) | Pass | API | |
| TC-EDGE-08 | Mở lại đơn nháp / chuyển tab hoá đơn có khách 0975961375 | Chỉ hiện huy hiệu Nợ, **không** bật hộp thoại | Pass (gán lại khách vào giỏ không qua ô tìm khách) | JS | |
| TC-EDGE-09 | Chọn khách 0975961375 rồi đổi ngay sang `a chinh` khi kết quả đầu chưa về | Chỉ hiện cảnh báo của a chinh | Pass | JS | |
| TC-EDGE-10 | Bấm **Thu nợ ngay** rồi đóng hộp Thu nợ **không thu** | Cảnh báo không mở lại; lần sau thu từ huy hiệu cũng không tự bật cảnh báo | Pass | JS | |
| TC-EDGE-11 | Thu nợ từ màn hình Công nợ / huy hiệu (không qua cảnh báo) cho khách đang trên giỏ | Huy hiệu tự cập nhật số mới, hộp thoại không tự bật | Pass (sau lần thu thật ACC-PAY-2026-00019/00020, huy hiệu = 154.900,01) | UI + JS | |
| TC-EDGE-12 | Thu ngân bấm ra ngoài ô tìm khách, POS tự khôi phục khách cũ | Không bật lại hộp thoại | Không áp dụng — bản POS hiện tại không có lối khôi phục (biến lưu khách cũ trong InvoiceCart không bao giờ được gán); code vẫn chặn sẵn bằng cờ `restored` | Đọc code | |
| TC-EDGE-13 | Mất mạng, chọn khách **chưa** có trong bản nạp sẵn | Không cảnh báo, bán bình thường, không báo lỗi | Pass | UI (vòng trước) | |
| TC-EDGE-14 | Máy chủ lỗi khi lấy công nợ | Không chặn bán; dùng bản lưu nếu có, không có thì thôi | Pass theo code (nhánh `catch` của store) — chưa tạo được lỗi máy chủ thật | Đọc code | |
| TC-EDGE-15 | *(vòng 2)* Ngưỡng = tổng nợ + 0,01 (154.900,02) → chọn khách 0975961375 | Không cảnh báo (cặp với TC-EDGE-07: so `>=`) | Pass (`show: false`) — 03/10/2026 | API (cấu hình giả lập trong bộ nhớ) | |
| TC-EDGE-16 | *(vòng 2)* Quầy đặt **Ẩn nợ lẻ dưới** (cấu hình của chức năng 1) = 1.000 → chọn khách 0975961375 | Đơn 00061 (còn 0,01) bị bỏ; cảnh báo còn 1 đơn, tổng 154.900. Danh sách nạp sẵn cho mất mạng cũng bỏ các khách chỉ nợ lẻ | Pass — 1 đơn / 154.900; nạp sẵn còn 4 khách (bỏ Admin-Hệ Thống 18, KH003779 19,99, KH008435 19, c le 19) — 03/10/2026 | API (cấu hình giả lập trong bộ nhớ, không ghi DB) | |
| TC-EDGE-17 | *(vòng 2)* Mã khách rỗng hoặc không tồn tại (`ZZ-KHONG-CO`) | Không cảnh báo, không báo lỗi | Pass (`show: false` cả hai) — 03/10/2026 | API | |
| TC-EDGE-18 | *(vòng 2)* Khai **Hạn mức công nợ** 100.000 cho khách 0975961375 ở company Chi Nhánh Sơn La → chọn khách | Ô Hạn mức 100.000, Còn được nợ 0, thanh tiến độ đỏ; ghi chú "…có 1 đơn quá hạn và vượt hạn mức…"; huy hiệu đỏ | Máy chủ Pass: `credit_limit 100000`, `over_limit: true` (ghi hạn mức trong giao dịch rồi rollback). Giao diện: Chưa chạy — chờ UI (Chrome cổng 8103) | API | |
| TC-EDGE-19 | *(vòng 2)* Hạn mức = **đúng** tổng nợ 154.900,01 | Không tính là vượt hạn mức (so `>`) | Pass (`over_limit: false`) — 03/10/2026 | API (rollback) | |
| TC-EDGE-20 | *(vòng 2)* Hạn mức khai cho **company khác** (Chi Nhánh Hà Đông) | Quầy Sơn La coi như không có hạn mức: "Không giới hạn" | Pass (`credit_limit: 0`) — 03/10/2026 | API (rollback) | |
| TC-EDGE-21 | *(vòng 2)* Khách **đang có tiền dư** (công ty nợ khách) nhưng còn vài đơn lẻ chưa cấn trừ: khách `1` (THU HUONG) — số dư sổ cái tại Sơn La **−479.371,6**; khách `84940297480` — đơn còn 17.700 nhưng sổ cái chỉ còn 6.000 | Theo đúng chữ của spec: cảnh báo vì "có ít nhất một hoá đơn còn nợ". **Cần anh Quân chốt** có nên trừ tiền dư/ứng trước chưa phân bổ trước khi cảnh báo không | Khúc mắc: API cảnh báo khách `1` có nợ **7.997,27 (7 đơn)** và nhắc "trả nợ trước khi bán tiếp", trong khi thực tế công ty đang nợ khách. Không ghi Pass/Fail cho tới khi chốt. **Anh Quân chốt 03/10: vẫn cảnh báo ("dư là dư, nợ là nợ") → Pass theo quyết định** | API + đối chiếu GL | |
| TC-EDGE-22 | *(vòng 2)* Nợ lẻ do **làm tròn** (đơn POS thu đúng `grand_total`, còn lệch tới `rounded_total` 15–25 ₫): Admin-Hệ Thống 18, KH008435 19, c le 19, KH003779 19,99 | Cấu hình mặc định (Ngưỡng 0, Ẩn nợ lẻ 0) vẫn bật hộp thoại cảnh báo cho các khoản 18–25 ₫ | Khúc mắc: đúng là có cảnh báo cho 5/8 khách đang nợ ở quầy, phần lớn là lệch làm tròn. Đề xuất hướng dẫn đặt Ẩn nợ lẻ (TC-EDGE-16) khi bật cảnh báo; gốc lệch làm tròn thuộc luồng thanh toán POS, không thuộc chức năng 2 | API + đọc Sales Invoice | |
| TC-EDGE-23 | *(vòng 2)* Quầy **tắt** cảnh báo (POS Hà Đông 02), user thuộc quầy gọi API nạp sẵn | `enabled: false`, danh sách rỗng — không lộ khách nợ | Pass — 03/10/2026 (`hangnt@mbw.vn`) | API | |
| TC-EDGE-25 | *(03/10)* Quầy đã **vô hiệu** (`disabled = 1`) dù còn tick Bật cảnh báo, gọi API | Coi như tắt cảnh báo: `show: false`, nạp sẵn `enabled: false` | Pass (giả lập trong bộ nhớ) — 03/10/2026 | API | |
| TC-EDGE-26 | *(03/10)* Dòng ghi chú về ghi nợ trong hộp cảnh báo theo POS Settings của quầy: (a) Cho bán chịu = 1 → (b) Cho bán chịu = 0, Trả một phần = 1 → (c) cả hai = 0 | (a) không có dòng ghi chú; (b) "Quầy này không cho ghi nợ toàn bộ: đơn mới khách phải trả trước ít nhất một phần."; (c) "Quầy này không bán chịu: đơn mới phải thanh toán đủ." — khớp luật chặn ở thanh toán (trả 0 cần bán chịu; trả một phần cần trả một phần HOẶC bán chịu) | Pass (a) trên màn hình (quầy đang Cho bán chịu = 1). (b)(c): chuỗi đã có trong bundle và vi.csv — **Cần người test** trên màn hình | UI + đọc bundle | |
| TC-EDGE-24 | *(vòng 2)* Đơn nợ bán từ **năm trước** | Cột Ngày bán / Hạn TT phân biệt được năm | Chưa chạy — site chưa có đơn nợ năm trước. Theo code hộp thoại chỉ hiện `dd/MM` (không có năm) → đơn 12/2025 và 12/2026 hiện giống nhau. **Đã sửa 03/10:** đơn khác năm hiện tại hiện `dd/MM/yy` | Đọc code | |

## TC-PERM — Phân quyền

Quyền của tính năng theo **POS Profile** (user phải nằm trong bảng người dùng của quầy), không theo User Permission chuẩn.

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-PERM-01 | Gọi API khi **chưa đăng nhập** (Guest) | HTTP 403, `You are not permitted to access this resource. Login to access` | Pass (403) | API (curl) | |
| TC-PERM-02 | User **không thuộc** quầy (`00191123@gmail.com`) gọi API cảnh báo và API nạp sẵn cho POS Chiềng Sại | Lỗi `You are not assigned to POS Profile POS Chiềng Sại` — không trả dữ liệu nợ | Pass (cả hai API) | API | |
| TC-PERM-03 | **Administrator** (không nằm trong bảng người dùng quầy) | Cũng bị chặn như TC-PERM-02 — không có ngoại lệ cho quản trị | Pass | API | |
| TC-PERM-04 | User thuộc quầy, có quyền thu (`tratthunguyen1215@gmail.com`, `hangnt@mbw.vn`) | Thấy cảnh báo và nút **Thu nợ ngay** | Pass | API + UI | |
| TC-PERM-05 | User thuộc quầy nhưng **không** có vai trò thu nợ | Thấy cảnh báo; không có nút Thu nợ ngay; có dòng "Bạn chỉ xem được công nợ. Thu nợ cần quyền thu nợ tại quầy này — nhờ quản lý hoặc thu ngân được cấp quyền." | Pass: giao diện (giả lập `can_collect = false`); máy chủ — Claude POS bỏ vai trò thu trong giao dịch rồi hoàn tác, API trả `show: true`, `can_collect: false`. Cần người test với user thật — quầy hiện không có user nào thiếu vai trò thu | JS + API | |
| TC-PERM-06 | User thuộc quầy A mở POS quầy A nhưng sửa request gửi `pos_profile` = quầy B mình không thuộc | Lỗi `You are not assigned to POS Profile <B>` | Pass (cùng nhánh kiểm với TC-PERM-02) | API | |
| TC-PERM-07 | Đơn nợ của khách ở **quầy khác cùng company** | Không tính vào cảnh báo của quầy này | Pass theo code (truy vấn dùng chung lọc theo quầy) — site chưa có khách nào chỉ nợ ở quầy khác cùng company | Đọc code + API | |
| TC-PERM-08 | *(vòng 2)* User có **User Permission POS Profile = POS Chiềng Sại** (và company Sơn La) nhưng **không** nằm trong bảng người dùng của quầy: `00192375@gmail.com` | Bị chặn cả API cảnh báo lẫn API nạp sẵn: `You are not assigned to POS Profile POS Chiềng Sại` | Pass — 03/10/2026 | API (`frappe.set_user`) | |
| TC-PERM-09 | *(vòng 2)* User bị giới hạn company **Chi Nhánh Hà Đông** (`nv1@vnpost.vn`, thuộc quầy POS Hà Đông 01) gọi API với quầy POS Chiềng Sại | Bị chặn như trên, không trả dữ liệu nợ của Sơn La | Pass — 03/10/2026 | API | |
| TC-PERM-10 | *(vòng 2)* User thuộc **2 quầy** (`hangnt@mbw.vn`: POS Chiềng Sại + POS Hà Đông 02) | Ở Chiềng Sại: đúng nợ của quầy Chiềng Sại (154.900,01 cho 0975961375). Ở Hà Đông 02 (tắt cảnh báo): không trả gì, kể cả khách `840975961375` đang nợ 934.000 ở Hà Đông | Pass — 03/10/2026 | API | |
| TC-PERM-11 | *(vòng 2)* User thuộc quầy nhưng **không có vai trò nào** trong 4 bảng quyền thu nợ của quầy (không có cả vai trò "xem công nợ" `Accounts User`) | Theo spec ("mọi thu ngân dùng quầy đã bật đều thấy cảnh báo"): vẫn thấy cảnh báo và danh sách đơn, không có nút Thu nợ ngay | Pass theo spec (`show: true`, `can_collect: false`, vai trò giả lập trong bộ nhớ). **Khúc mắc:** cảnh báo + nạp sẵn bỏ qua bảng "vai trò xem công nợ" của chức năng 1 → thu ngân không được xem màn Công nợ vẫn xem được toàn bộ khách nợ của quầy qua cảnh báo / bản nạp sẵn. Anh Quân chốt 03/10: giữ theo tài liệu (mọi thu ngân của quầy thấy cảnh báo) → Pass | API | |
| TC-PERM-12 | *(vòng 2)* Bản nạp sẵn cho mất mạng nằm trong trình duyệt: đăng xuất (hoặc đóng ca) rồi mở DevTools → Application → IndexedDB `pos_next_offline` → bảng `customer_debts` | Đề xuất: dữ liệu nợ (tên, SĐT, số nợ, mã đơn) bị xoá khi đăng xuất | Chưa chạy — chờ UI (Chrome cổng 8103). Theo code: không có chỗ nào xoá bảng này khi đăng xuất / đóng ca (`clearAllCache` không gồm `customer_debts`). **Đã sửa 03/10 (Claude Pos Next 1, build 09:44):** mỗi dòng ghi kèm `user`; mở POS xoá dòng của tài khoản khác (đã thử: dòng giả `zz-other@test` bị xoá sau khi tải lại); đóng ca xoá dòng của quầy; đăng xuất xoá hết — chờ chạy lại vòng 2 | Đọc code | |

## TC-REGR — Không làm hỏng luồng đang chạy

| Mã | Bước thực hiện | Kết quả mong đợi | Kết quả thực tế | Cách kiểm | Người kiểm |
|---|---|---|---|---|---|
| TC-REGR-01 | Chọn khách → thêm hàng → thanh toán đủ | Bán bình thường, hoá đơn tạo được; cảnh báo không chặn thanh toán | Cần người test — chưa chạy thanh toán thật lần này | — | |
| TC-REGR-02 | Chọn khách có ưu đãi theo nhóm khách | Ưu đãi vẫn áp như trước | Cần người test | — | |
| TC-REGR-03 | Quầy **tắt** cảnh báo, bấm huy hiệu Nợ (của chức năng 1) | Mở thẳng hộp Thu nợ như trước khi có chức năng 2 | Pass theo code (DebtBadge `warningEnabled = false` → `open-collect`) | Đọc code | |
| TC-REGR-04 | Hook trên Customer / POS Profile của pos_next | Chức năng 2 không thêm hook nào (`hooks.py` không đổi vì chức năng 2) | Pass | Đọc code | |
| TC-REGR-05 | *(vòng 2)* Máy đang có **hoá đơn offline chưa đồng bộ**, mở bản POS mới (có thêm bảng `customer_debts` trong IndexedDB) | Bảng mới được thêm, hoá đơn offline chờ đồng bộ **không mất**, đồng bộ được khi có mạng | Chưa chạy — chờ UI (Chrome cổng 8103) | — | |
| TC-REGR-06 | *(vòng 2)* Tải máy chủ của API nạp sẵn lúc mở ca / mỗi lần có mạng lại | Không làm chậm mở ca | Pass ở quy mô hiện tại: 8 khách, 0,02 s, ~44 truy vấn (~5,5 truy vấn/khách). Lưu ý: tối đa 1.000 khách ≈ 5.500 truy vấn mỗi lần mở ca **và mỗi lần mạng chập chờn có lại** — cần thử ở site thật nhiều khách nợ. **Đã sửa 03/10:** lọc sẵn khách bằng SQL (bỏ khách lẻ, nhóm loại trừ, tổng nợ < ngưỡng, ẩn nợ lẻ) rồi mới giới hạn 1.000; nạp lại tối đa 10 phút một lần, trừ khi mở ca / đổi quầy. Kiểm lại: 8 khách (khớp trước), ngưỡng 50.000 → 2, loại Individual → 6 | API (đếm truy vấn) | |

## TC-ISO — Cô lập

| Mã | Kiểm tra | Kết quả mong đợi | Kết quả thực tế | Người kiểm |
|---|---|---|---|---|
| TC-ISO-01 | 3 custom field của POS Profile có `module = POS Next` | Đúng | Pass | |
| TC-ISO-02 | `git status` của frappe | Sạch | Pass | |
| TC-ISO-03 | `git status` của erpnext | Không có file do chức năng 2 sửa | Pass — erpnext đang có `bank_transaction.json/.py` sửa sẵn, **không** liên quan chức năng này | |
| TC-ISO-04 | Mọi chuỗi hiển thị có bản dịch trong `pos_next/translations/vi.csv` | Đủ | Pass (27/27 chuỗi; đã bổ sung "POS Profile is required") | |
| TC-ISO-05 | Giao diện tiếng Việt hiển thị đúng chữ | Đúng chữ, không tràn | Pass (03/10/2026, POS và Desk đang ở tiếng Việt): hộp cảnh báo, huy hiệu "Nợ … · Quá hạn", dải mất mạng, dòng chỉ được xem, tab Thu nợ của POS Profile đều đúng chữ, không tràn. Ảnh: docs/mockups/canh-bao-cong-no-khi-chon-khach-ban-code.html | |
| TC-ISO-06 | *(vòng 2)* DocType con `POS Profile Customer Group` | `module = POS Next`, `istable = 1`, không phải custom | Pass — 03/10/2026 | |
| TC-ISO-07 | *(vòng 2)* Site khác có cài pos_next nhưng **chưa migrate** (`retail.mbwnext`, `gosumo.havang` — chưa có cột `posa_enable_debt_warning`) | POS vẫn bán bình thường: store coi cảnh báo là tắt (`posa_enable_debt_warning` không có → `enabled = false`), không gọi API. Gọi API trực tiếp sẽ lỗi SQL → khi deploy **bắt buộc migrate** | Pass theo code (đã xác nhận 2 site chưa có cột) — chưa mở POS trên 2 site đó | |
| TC-ISO-08 | *(vòng 2)* Chuỗi dịch của `DebtWarningDialog.vue`, `stores/debtWarning.js`, `api/debt_warning.py` | Đủ trong `vi.csv` | Pass (25/25 chuỗi) — 03/10/2026 | |

## Dọn dẹp sau khi chạy

- Cấu hình POS Chiềng Sại để lại: Bật cảnh báo = 1, Ngưỡng = 0, Nhóm loại trừ = trống (đã trả về sau TC-HAPPY-11 / TC-EDGE-05).
- Các ca giả lập cấu hình (TC-EDGE-03/04/06/07) chạy trong bộ nhớ, không ghi DB.
- Không tạo Payment Entry nào trong vòng 1. Hai phiếu ACC-PAY-2026-00019/00020 do chức năng 1 tạo khi thử thu nợ thật.
- Giỏ hàng trên tab thử đã bỏ khách.

## Vòng 2 — Claude Pos Next 2 (03/10/2026)

Rà soát chéo + chạy lại phía máy chủ trên `pos.next` (script Python nạp `frappe` trực tiếp, `frappe.set_user` từng user, **luôn rollback**, không commit; cấu hình ngưỡng / ẩn nợ lẻ / vai trò giả lập trong bộ nhớ; hạn mức ghi tạm trong giao dịch rồi rollback — đã kiểm không còn bản ghi). Không tạo / sửa chứng từ nào. Ca giao diện để phiên chính chạy bằng Chrome trên cổng riêng http://localhost:8103/pos.

**Chạy lại case cũ (API):** TC-VALID-01, TC-VALID-02, TC-HAPPY-01…04 (số liệu: 2 đơn, 154.900,01, 1 quá hạn — số ngày tăng 1 so với vòng 1 vì chạy ngày 03/10), TC-HAPPY-11, TC-EDGE-01…07, TC-PERM-02/03 (thêm user `00192375@gmail.com`, `nv1@vnpost.vn`, Guest), TC-PERM-04 (cả `hangnt@mbw.vn`), TC-PERM-05, TC-PERM-06 — **đều Pass**, khớp vòng 1.

**Case mới:** TC-EDGE-15…24, TC-PERM-08…12, TC-REGR-05/06, TC-ISO-06…08 (ghi ở các bảng trên, đánh dấu *(vòng 2)*).

**Khúc mắc phát hiện (chưa sửa code — báo phiên phụ trách):**

| # | Mức | Nội dung | Chỗ trong code |
|---|---|---|---|
| 1 | Trung bình — cần chốt nghiệp vụ | Khách đang có tiền dư / ứng trước chưa cấn trừ vẫn bị cảnh báo "còn nợ" theo từng đơn (khách `1`: cảnh báo 7.997,27 trong khi sổ cái công ty nợ khách 479.371,6). Truy vấn dùng chung chỉ nhìn `outstanding_amount` từng hoá đơn | `debt_collection._base_debt_query` (chức năng 1), dùng lại ở `debt_warning._build_warning:110` |
| 2 | Trung bình — cần chốt | Cảnh báo và bản nạp sẵn **không xét vai trò "xem công nợ"** của chức năng 1: thu ngân bị chặn màn Công nợ vẫn thấy toàn bộ khách nợ (tên, SĐT, số nợ) qua cảnh báo, và cả danh sách được tải về máy lúc mở ca. Đúng chữ spec ("mọi thu ngân thấy cảnh báo") nhưng lệch tinh thần phân quyền của chức năng 1 | `debt_warning.get_customer_debt_warning:26`, `get_profile_debtors:33` |
| 3 | Thấp–Trung bình | Bản nạp sẵn trong IndexedDB không xoá khi đăng xuất / đóng ca → máy dùng chung (máy tính bảng quầy) giữ dữ liệu nợ của khách | `stores/debtWarning.js:149` (`preload`), `utils/offline/cache.js:304` (`clearAllCache` không gồm bảng) |
| 4 | Thấp | Nợ lẻ do làm tròn (15–25 ₫) gây cảnh báo ở cấu hình mặc định (5/8 khách nợ của POS Chiềng Sại). Cần hướng dẫn đặt "Ẩn nợ lẻ" khi bật cảnh báo; gốc lệch nằm ở luồng thanh toán POS | dữ liệu ACC-SINV-2026-00089/00090/00091/00096 |
| 5 | Thấp (hiệu năng) | Nạp sẵn chạy `_build_warning` cho từng khách (~5,5 truy vấn/khách, tối đa 1.000 khách) mỗi lần mở ca và **mỗi lần có mạng lại**; danh sách ứng viên lấy `limit 1000` trước khi áp ẩn nợ lẻ / nhóm loại trừ / ngưỡng | `debt_warning.py:39-57`, watcher `stores/debtWarning.js:215` |
| 6 | Thấp | Cột ngày trong hộp thoại chỉ `dd/MM`, không có năm | `DebtWarningDialog.vue:152` |
| 7 | Thấp | `_get_profile` của cảnh báo không kiểm quầy bị vô hiệu (`disabled`) — chỉ ảnh hưởng gọi API trực tiếp | `debt_warning.py:62` |

**Trạng thái sau bản sửa 03/10 (Claude Pos Next 1):** #1 và #2 — anh Quân chốt giữ (vẫn cảnh báo; quyền theo tài liệu). #3, #5, #6, #7 — đã sửa (xem TC-PERM-12, TC-REGR-06, TC-EDGE-24, TC-EDGE-25). #4 — không sửa code, ghi vào HDSD cấu hình (đặt Ẩn nợ lẻ khi bật cảnh báo).

Không thấy lỗi ở: so ngưỡng `>=`, so hạn mức `>`, hạn mức theo company, loại nhóm con, lọc company / quầy, chặn user không thuộc quầy (kể cả Administrator, user có User Permission đúng quầy nhưng không nằm trong bảng user quầy), khách rỗng / không tồn tại, quầy tắt cảnh báo.

**Còn chờ giao diện (Chrome cổng 8103):** TC-EDGE-18 (hạn mức vượt — giả lập bằng JS), TC-EDGE-21 (xem khách `1` trên màn hình), TC-PERM-12, TC-REGR-01, TC-REGR-02, TC-REGR-05. TC-HAPPY-10 cần một lần thu hết nợ thật — chỉ chạy khi phiên chức năng 1/anh Quân đồng ý tạo Payment Entry.

**Dọn dẹp vòng 2:** không ghi DB (mọi script kết thúc bằng rollback; bản ghi hạn mức tạm `zz-test-ccl` đã kiểm không tồn tại sau rollback). Cấu hình POS Chiềng Sại giữ nguyên: Bật cảnh báo = 1, Ngưỡng = 0, Nhóm loại trừ = trống, Ẩn nợ lẻ = 0.

### Vòng 2b — chạy lại sau bản sửa 03/10 (build 09:44), Claude Pos Next 2

| Mã | Kết quả thực tế | Cách kiểm |
|---|---|---|
| TC-PERM-12 | **Pass phần mở lại POS**: mỗi dòng `customer_debts` ghi kèm `user` (8 dòng, đều `tratthunguyen1215@gmail.com`). Chèn giả 1 dòng của `zz-other@test.local` rồi tải lại POS → dòng đó bị xoá, còn 8 dòng. Phần **đăng xuất** (xoá hết) và **đóng ca** (xoá dòng của quầy): **Cần người test**, vì đăng xuất phải đăng nhập lại bằng mật khẩu, còn đóng ca sẽ đóng ca thật đang dùng chung | UI + JS (cổng 8103, 09:46) |
| TC-EDGE-24 | **Pass theo hàm định dạng**: `2026-12-05` → `05/12`, `2025-12-05` → `05/12/25`, `2026-07-25 10:00:00` → `25/07`. Site chưa có đơn nợ năm trước để xem trên màn hình | Chạy hàm `dayMonth` của `DebtWarningDialog.vue` bằng node |
| TC-EDGE-21, TC-PERM-11 | Anh Quân chốt (phiên Claude Pos Next 1 ghi): khách có tiền dư vẫn cảnh báo; quyền thấy cảnh báo theo tài liệu. Màn hình 09:20 đã thấy khách `1` bị cảnh báo 7.997,27 / 7 đơn, đúng quyết định | UI (cổng 8103) |
