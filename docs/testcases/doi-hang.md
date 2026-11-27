# Test case — Đổi trả hàng trên POS

| | |
|---|---|
| App | `pos_next` (nhánh `feat/doi-hang`, tách từ `develop` 9263e4b) |
| DocType liên quan | Sales Invoice, POS Return Reason (mới), POS Settings, POS Profile, Journal Entry, Wallet Transaction, Loyalty Point Entry |
| Đầu bài + spec | `docs/features/doi-hang.md` (mục 0 đã chốt, mục 6 spec đợt 1) |
| Mockup | `docs/mockups/doi-hang.html` (bản 2) |
| PM | PM-FEAT-00060 · PM-PRJ-00025 · lỗi tách riêng PM-TASK-00267 |
| Người viết / Ngày | Claude (phiên Pos app chung) / 2026-10-07 |

## Điều kiện chuẩn bị

- **Môi trường:** develop — `http://mbw.com:8009/pos` (bench `mbwnext_account_ha`, site `mbw.com`),
  `pos_next` ở nhánh `feat/doi-hang`.
- **Tài khoản:**
  - `Administrator` / mật khẩu Administrator của site dev (hỏi anh Quân). Có ca POS đang mở
    `POSA-OS-26-0000657` ở cửa hàng **HAN_PAZZION HN CENTRE**.
  - TC-PERM tầng dữ liệu: `danjohn.diamond@havang.com`, vai trò `POSNext Cashier`, bị User Permission
    giới hạn **chỉ POS Profile `HCM_DANJOHN DIAMOND`**.
- **Cách vào tính năng:**
  - Màn hình bán POS → nút **Return Invoice / Trả hàng** (ở giỏ trống hoặc menu tài khoản) → hộp
    thoại **Đổi / Trả hàng**.
  - Hoặc: **Invoice History / Lịch sử hóa đơn** → nút trả (mũi tên quay lại) trên dòng hóa đơn.
- **Dữ liệu cần có:**
  - Hóa đơn gốc: 2 đôi giày **10113010** và **10119576** (3.199.000 / đôi), KM tổng đơn 10% theo
    Pricing Rule **PRLE-70942** (đơn từ 5.000.000), tổng **5.758.200**, khách **05000839**. Tạo bằng
    `docs/testcases/data/doi_hang.py`.
  - Hàng mới để đổi: **10113012** (3.199.000, đổi cùng giá), **test km 310** (5.000.000, đắt hơn),
    **10116849** (1.999.000, rẻ hơn).
  - Chương trình điểm **NEW-2026**: 100.000đ = 1 điểm. Cửa hàng HAN_PAZZION bật "điểm chuyển thành
    tiền ví". Hệ số quy đổi trên site dev là 1đ/điểm. Ca E2 đổi tạm thành 1.000đ/điểm trong lúc thử.
  - 4 lý do trả mặc định do patch tạo: Không vừa size, Lỗi sản phẩm (kho hàng lỗi), Khách đổi ý,
    Giao nhầm hàng.
- **Dữ liệu tự tạo cho test:**
  - Ca chạy bằng server: tạo rồi **hoàn tác** sau mỗi lần chạy, không để lại gì. Đã kiểm 0 hóa đơn
    `AC261007*` còn lại.
  - Ca bấm trên giao diện ngày 06/10 **còn trên site**: AC2610060001–0008, ghi chú "THỬ PM-FEAT-00060"
    (xem spec mục 6.9).

**Cách Claude kiểm chứng (cột KQ thực tế):**
- **[API]** gọi thẳng `pos_next.api.exchange` qua `bench execute` trên dữ liệu thật rồi hoàn tác.
- **[UI]** bấm trên Chrome thật, tài khoản Administrator.
- Hai cách này không thay thế nhau. Người test lại tay chạy theo cột "Bước thực hiện".

## Bảng test case

### TC-HAPPY — Luồng đúng

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-HAPPY-01 | Chỉ trả hàng, đơn mất KM ngưỡng | 1. Bấm Trả hàng → chọn HĐ gốc. 2. Tick đôi 10119576, SL 1, lý do Khách đổi ý → Tiếp. 3. Chọn **Trả hàng, hoàn tiền**. 4. Xem bảng Tính lại đơn → Hoàn tất | HĐ gốc 5.758.200 | Hoàn **2.559.200** (= 5.758.200 − 3.199.000). Dòng "Đơn còn dưới 5.000.000: thu hồi KM −319.900". HĐ gốc hết công nợ | [UI] AC2610060004: hoàn 2.559.200, thu hồi 319.900, điểm 57→28 thu 29đ ví. [API] S3 giống hệt | Pass |
| TC-HAPPY-02 | Đổi cùng giá (đổi size) | 1–2 như trên, lý do Không vừa size. 3. Chọn **Đổi sang hàng khác**. 4. Màn hình bán: quét 10113012. 5. Dải vàng / ô tổng của giỏ → Thanh toán → Hoàn tất | HĐ gốc, hàng mới 10113012 | Dải vàng: **Chênh lệch 0đ · Giữ KM đơn gốc**. Thanh toán: "Không phát sinh thanh toán". Tạo phiếu trả + HĐ mới, HĐ mới có CK 319.900, tổng 2.879.100, đã trả đủ | [UI] AC2610060005 + AC2610060006: chênh 0, HĐ mới CK 319.900, còn nợ 0 | Pass |
| TC-HAPPY-03 | Đổi sang hàng đắt hơn | Như 02, hàng mới **test km 310** | 5.000.000 | Khách trả thêm **1.801.000** (= 5.000.000 − 3.199.000). Ô Tiền mặt điền sẵn 1.801.000 | [UI] (đổi nối tiếp, xem EDGE-05) AC2610060008: khách trả 1.801.000. [API] S2 giống | Pass |
| TC-HAPPY-04 | Đổi sang hàng rẻ hơn — cửa hàng cấu hình **Hoàn tiền** | Như 02, hàng mới 10116849. Cài đặt POS: "Khi đổi sang hàng rẻ hơn" = Hoàn tiền | 1.999.000 | Trả lại khách **1.200.000**, nhập tiền hoàn theo hình thức | [API] hoàn 1.200.000 tiền mặt, phiếu trả đã chi 1.200.000, HĐ gốc còn nợ 0 | Pass |
| TC-HAPPY-05 | Rẻ hơn — cấu hình **Ghi vào số dư khách** (cửa hàng bật bán chịu / số dư) | Như 04, đổi cấu hình | | Ghi 1.200.000 vào số dư khách, không chi tiền. Ở màn thanh toán lần mua sau, khoản này hiện **1 lần** | [API] lần 1 **Fail**: số dư hiện 2 lần (HĐ gốc + phiếu trả), tách PM-TASK-00267. Đã sửa `credit_sales` đọc theo sổ công nợ. Lần 2 (14/10): 1 nguồn duy nhất là HĐ gốc 1.200.000 | Pass (sau sửa) |
| TC-HAPPY-06 | HĐ còn nợ: giảm nợ trước | Tạo HĐ gốc chỉ trả 2.000.000 (nợ 3.758.200). Trả đôi 10119576 | | Không chi tiền. Nợ HĐ gốc còn **1.199.000** | [API] S4: không chi, nợ còn 1.199.000 | Pass |
| TC-HAPPY-07 | Lý do **Lỗi sản phẩm** → kho hàng lỗi | Khai "Kho hàng lỗi" trên POS Profile. Trả hàng, chọn lý do Lỗi sản phẩm | | Hàng nhập vào **kho hàng lỗi**, không vào kho bán | [API] lần 1 **Fail**: nhập kho bán (ERPNext ghi đè kho). Đã sửa `update_invoice`. Lần 2: sổ kho +1 ở kho hàng lỗi | Pass (sau sửa) |
| TC-HAPPY-08 | Thu hồi tiền ví từ điểm — ví đủ | Trả hàng của HĐ đã tích điểm vào ví | 57 điểm | Điểm HĐ gốc 57→28, trừ ví 29 (theo hệ số) | [UI]+[API] 57→28, trừ ví 29đ | Pass |
| TC-HAPPY-09 | Thu hồi tiền ví — khách **đã tiêu** gần hết ví | Hệ số 1.000đ/điểm, ví còn 5.000 | | Thu 29.000: trừ ví 5.000, **24.000 trừ vào tiền hoàn** → hoàn 2.535.200. Bút toán Nợ 131 / Có TK chi phí điểm | [API] đúng như mong đợi, HĐ gốc còn nợ 0 | Pass |

### TC-VALID — Bị chặn và câu thông báo

Câu thông báo tiếng Anh chép nguyên văn từ code, tiếng Việt theo `translations/vi.csv`.

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-VALID-01 | Trả lần 2 trên cùng HĐ | Mở HĐ đã đổi trả | | Dòng xám nhãn *Already returned once*. Gọi thẳng: *Invoice {0} was already returned / exchanged on {1} ({2}). Each invoice can only be returned once.* | [UI] dòng xám đúng. [API] đúng câu | Pass |
| TC-VALID-02 | Quá hạn đổi trả | Hạn 3 ngày, HĐ 5 ngày trước | | *Return period has expired. Invoice {0} was created {1} days ago. Returns are only allowed within {2} days of purchase.* Không có nút duyệt vượt | [API] đúng câu | Pass |
| TC-VALID-03 | Kỳ đã khóa sổ | Khóa sổ tới hôm nay | | *Invoice {0} belongs to a closed accounting period (up to {1}). It cannot be returned.* | [API] đúng câu | Pass |
| TC-VALID-04 | Trả ở cửa hàng khác | Gọi với POS Profile khác | | *Invoice {0} was sold at another store ({1}). Returns are only accepted at the store that sold it.* | [API] đúng câu | Pass |
| TC-VALID-05 | Cửa hàng tắt "Cho phép trả hàng" | Tắt Allow Return trong Cài đặt POS | | Bấm nút Trả hàng → cảnh báo *Returns are disabled for this store.* | [API] chặn đúng câu. Nút trên giao diện: **Chưa chạy** | Pass (API) |
| TC-VALID-06 | Chưa chọn lý do | Bỏ trống lý do | | Nút Tiếp xám. Gọi thẳng: *Please select a return reason.* | [UI] nút xám. [API] đúng câu | Pass |
| TC-VALID-07 | Lý do hàng lỗi khi chưa khai kho hàng lỗi | | | Lựa chọn "Lỗi sản phẩm" bị khóa, kèm dòng giải thích. Gọi thẳng: *Reason {0} sends items to the Defective Warehouse, but POS Profile {1} has no Defective Warehouse.* | [UI] bị khóa. [API] đúng câu | Pass |
| TC-VALID-08 | Trả quá số đã mua | SL 2 trên dòng mua 1 | | *You are trying to return more {0} than was sold.* | [API] đúng câu. Giao diện giới hạn ô SL tối đa = số đã mua | Pass |
| TC-VALID-09 | Số lẻ với ĐVT bắt số nguyên | SL 0,5 Đôi (Đôi bật "phải là số nguyên") | | *{0} must be returned in whole {1}.* | [API] đúng câu. ⚠ Trên site, ĐVT **Cái / Đôi chưa bật** "phải là số nguyên", nên mặc định vẫn cho trả lẻ | Pass (cần sửa dữ liệu ĐVT) |
| TC-VALID-10 | Hàng dịch vụ | Trả dòng hàng không quản kho | | *{0} is a service item and cannot be returned.* | [API] **Chưa chạy**: site không có mã hàng dịch vụ | Chưa chạy |
| TC-VALID-11 | Đổi rẻ hơn, cấu hình **Bắt lấy thêm** | | | Không hoàn tất được: *This store does not refund when exchanging for cheaper items. The customer needs to pick at least {0} more.* | [API] đúng câu, thiếu 1.200.000 | Pass |
| TC-VALID-12 | Quỹ tiền mặt ca không đủ | Hoàn tiền mặt > tiền mặt trong ca | Quỹ 1.000.000, hoàn 2.559.200 | *Cash in this shift is {0}, not enough to refund {1} in cash. Refund by bank transfer or add it to the customer's balance.* Chia 900.000 tiền mặt + còn lại chuyển khoản thì lưu được | [API] đúng | Pass |
| TC-VALID-13 | Nhập tiền hoàn thiếu | Thiếu 100.000 | | Nút Hoàn tất xám. Gọi thẳng: *Refund payments ({0}) must equal the refund amount ({1}).* | [API] đúng câu | Pass |
| TC-VALID-14 | Khách trả thêm thiếu | Thiếu 100.000 | | *Customer still needs to pay {0}.* | [API] đúng câu | Pass |
| TC-VALID-15 | Không có ca mở | | | *Please open a shift before returning items.* | [API] đúng câu | Pass |
| TC-VALID-16 | Số trên màn hình lệch server | Gửi chênh lệch dự kiến sai | | *The amounts changed while you were working (expected {0}, now {1}). Please review and try again.* Không lưu gì | [API] đúng câu | Pass |

### TC-EDGE — Biên, lặp, hủy

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-EDGE-01 | HĐ mới lỗi giữa chừng | Giả lập lỗi khi lưu HĐ mới | | Phiếu trả cũng được hoàn tác, **không** có phiếu trả mồ côi | [API] 0 phiếu trả còn lại | Pass |
| TC-EDGE-02 | Không treo công nợ / số dư ảo sau đổi trả | Sau mỗi luồng 01–06, xem nguồn tiền của khách | | Không có nguồn tiền nào sinh ra từ lần đổi (trừ khi chọn ghi có) | [UI] lần 1 **Fail**: phiếu trả giữ −2.879.100, khách hiện số dư 2.879.100. Đã sửa. [API] lại: 0 nguồn tiền ở cả 5 kịch bản | Pass (sau sửa) |
| TC-EDGE-03 | Hủy riêng phiếu trả | Cancel phiếu trả của lần đổi | | Bị chặn vì HĐ mới liên kết | [API] *Cannot delete or cancel because Sales Invoice … is linked with Sales Invoice …* | Pass |
| TC-EDGE-04 | Hủy cả bộ theo thứ tự | Cancel bút toán → HĐ mới → phiếu trả | | HĐ gốc trở lại như cũ, đổi trả lại được | [API] HĐ gốc còn nợ 0, tính lại được | Pass |
| TC-EDGE-05 | Đổi nối tiếp (A → B → C) | Mở HĐ mới của lần đổi trước, đổi tiếp | AC2610060006 | Giá "khách thực trả" lấy theo lần đổi trước (2.879.100) | [UI] AC2610060007 + 0008, khách trả 1.801.000 | Pass |
| TC-EDGE-06 | Hủy riêng HĐ mới | Cancel HĐ mới | | Bút toán chuyển tiền tự hủy. Khách còn 2.879.100 ghi có trên HĐ gốc, hiện **1 lần** | [API] đúng như mong đợi | Pass |
| TC-EDGE-07 | Hủy đổi hàng giữa chừng | Vào chế độ đổi hàng, thêm hàng, bấm **Hủy đổi hàng** | | Thoát chế độ đổi, giỏ trống, Grand Total 0 | [UI] thoát được nhưng **Grand Total −500.000** (lỗi có sẵn ở xóa giỏ). Đã sửa `useInvoice.clearCart/resetInvoice`. **Chưa thử lại trên giao diện** | Chưa chạy lại |
| TC-EDGE-08 | Ô tổng của giỏ khi đang đổi hàng | Đổi sang hàng 5.000.000 | | Ô tổng hiện **Khách trả thêm 1.801.000**, ẩn dòng KM / coupon của giỏ | [UI] đúng | Pass |
| TC-EDGE-09 | Quà tặng đi kèm | HĐ có quà tặng, tick hàng chính | | Quà tự tick theo, khóa | **Chưa chạy**: chưa có HĐ có quà tặng trên dữ liệu thử | Chưa chạy |
| TC-EDGE-10 | Tiêu khoản ghi có một lần | Sau HAPPY-05, bán HĐ mới 1.999.000 cho cùng khách, thanh toán bằng số dư khách | khách 05000839 | Trừ 1.200.000, HĐ mới còn nợ 799.000; số dư khách về 0 | [API] HĐ mới còn 799.000, nguồn tiền còn lại: rỗng | Pass |
| TC-EDGE-11 | Không tiêu lại được khoản đã tiêu | Tiếp EDGE-10, thử dùng số dư lần nữa | | Bị chặn: *Insufficient credit available from …* | [API] chặn | Pass |
| TC-EDGE-12 | Không tiêu được theo tên phiếu trả | Gửi yêu cầu tiêu số dư với nguồn là phiếu trả (màn hình cũ / dữ liệu cũ) | | Bị chặn, số khả dụng 0 — tiền chỉ nằm ở HĐ gốc | [API] chặn: *Insufficient credit available from AC2610140002. Available: VND 0,00* | Pass |

### TC-PERM — Phân quyền

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-PERM-01 | Thu ngân dùng được danh mục lý do | Đăng nhập thu ngân, mở hộp thoại | `danjohn.diamond@havang.com` | Thấy 4 lý do, **không** tạo được lý do mới | [API] đọc 4, quyền tạo = False | Pass |
| TC-PERM-02 | Danh sách HĐ cửa hàng mình | Thu ngân bị giới hạn mở danh sách | `HCM_DANJOHN DIAMOND` | Số HĐ khớp `frappe.get_list` dưới đúng user | [API] 29 = 29 | Pass |
| TC-PERM-03 | Xem danh sách HĐ cửa hàng khác (sửa tham số) | Gọi với POS Profile khác | `HAN_PAZZION HN CENTRE` | Chặn: *You do not have access to POS Profile {0}.* | [API] lần đầu đọc code thấy **rò rỉ** (truy vấn thô). Đã sửa sang `frappe.get_list`. Nay chặn | Pass (sau sửa) |
| TC-PERM-04 | Mở / tính đổi HĐ cửa hàng khác | | AC2610060003 | Chặn PermissionError | [API] cả hai bị chặn | Pass |
| TC-PERM-05 | Administrator không bị ảnh hưởng | | | Thấy đủ | [API] 50 HĐ | Pass |

### TC-REGR — Hồi quy

Các app khác cùng hook Sales Invoice (`grep hooks.py`):
- `mbwnext_advanced_selling`: chặn hàng ngừng kinh doanh, tài khoản thanh toán POS.
- `mbwnext_advanced_accounting`: bút toán chênh thuế, Sales Voucher.
- `mbwnext_gosumo`: CK theo Pricing Rule.
- `pos_next`: ví, loyalty.

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-REGR-01 | Bán thường vẫn tự áp KM tổng đơn | Bán test km 310, không gửi KM | 5.000.000 | Tổng 4.500.000, CK 500.000 (ERPNext tự áp như trước) | [API] đúng | Pass |
| TC-REGR-02 | Trả hàng theo đường cũ (`submit_invoice`) | | | Lưu được, không cấp mã tự xuất HĐĐT cho phiếu trả | [API] phiếu trả −2.879.100 | Pass |
| TC-REGR-03 | Bảng kê HĐĐT cuối ngày | Danh sách HĐ chưa xuất của ngày | | Có cả HĐ gốc + phiếu trả cùng ngày. Gửi riêng phiếu trả thì chặn: *{0}: Phiếu trả hàng của {1} chỉ được gộp cùng bảng kê với hóa đơn gốc.* | [API] đúng | Pass |
| TC-REGR-04 | Đóng ca | Dựng dữ liệu đóng ca có phiếu đổi trả | ca 0000657 | Dựng được, đếm đúng phiếu trả | [API] 10 chứng từ, 3 phiếu trả | Pass |
| TC-REGR-05 | Đơn vẫn tính điểm như trước | | | Hóa đơn bán vẫn tích điểm → ví | [API] HĐ thử có 57 điểm, cộng ví | Pass |
| TC-REGR-06 | Hàng ngừng kinh doanh vẫn bị chặn trả (F6) | Trả mã đã khóa kinh doanh | | Bị chặn bởi `mbwnext_advanced_selling` | **Chưa chạy** | Chưa chạy |

### TC-ISO — Cách ly

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-ISO-01 | Custom Field đi theo app | Xem `module` của 4 field mới | | Đều = `POS Next` | đúng | Pass |
| TC-ISO-02 | Không lọt sang app khác | `git status` các app lõi trên bench | | Sạch | 10 app, 0 file thay đổi | Pass |
| TC-ISO-03 | Site cũ không mất trả hàng sau cập nhật | Patch `bat_cho_phep_tra_hang` | 46 Cài đặt POS tắt | Bật lại cả 46, cửa hàng vẫn trả hàng như cũ | [API] bật 46/46 | Pass |
| TC-ISO-04 | Bench khác dùng `pos_next` (cozy_dev, vnpost, test_core) | | | Không áp dụng lúc này: các bench đó chưa lấy nhánh `feat/doi-hang`. Chạy khi merge | — | Không áp dụng |

TC-PWA: không áp dụng. POS Next không có màn hình mobile riêng cho tính năng này, và đổi trả bắt buộc online.

## Kết luận

- **Tổng:** 52 ca.
  - **Pass:** 47, trong đó 5 ca Pass sau khi sửa lỗi tìm ra lúc test (HAPPY-05, HAPPY-07, EDGE-02, PERM-03,
    VALID-09 cần sửa dữ liệu ĐVT). VALID-05 mới Pass ở API, nút trên giao diện chưa thử.
  - **Fail:** 0. HAPPY-05 Fail ở lần 1 do lỗi có sẵn PM-TASK-00267, đã sửa ngày 14/10 và chạy lại Pass.
  - **Chưa chạy / chưa chạy lại:** 4 (VALID-10, EDGE-07, EDGE-09, REGR-06).
  - **Không áp dụng:** 1 (ISO-04).
- **Lỗi tìm ra khi test và đã sửa:**
  - Số dư khách ảo sau đổi hàng.
  - Hàng lỗi vào sai kho.
  - Rò rỉ danh sách HĐ cửa hàng khác.
  - Giỏ trống hiện số âm.
  - Giỏ hiện sai tổng khi đang đổi hàng.
  - Số dư khách tính 2 lần khi ghi có (PM-TASK-00267): đọc số dư theo sổ công nợ thay cho trường còn nợ của hóa đơn.
- **Lỗi còn lại:**
  - Dữ liệu ĐVT "Cái / Đôi" chưa bật "phải là số nguyên".
- **Đủ điều kiện nghiệm thu:** **chưa**. Còn chờ:
  - Người test chạy lại tay, và chạy nốt các ca "Chưa chạy".
