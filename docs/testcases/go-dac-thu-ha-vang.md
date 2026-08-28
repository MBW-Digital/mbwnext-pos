# Test case — Gỡ code đặc thù Hạ Vàng khỏi develop

| | |
|---|---|
| App | `pos_next` |
| DocType liên quan | Sales Invoice, POS Profile, Print Format, Company, Wallet Transaction |
| Đầu bài | Không có file spec — việc phát sinh sau khi merge nhánh `ha_vang` (`2897323`) vào `develop` |
| Commit | `b97bc05`, `038c47e`, `b5ea801`, `dcfc195`, `18514fe` |
| Người viết / Ngày | Claude / 2026-08-28 |

## Phạm vi

Merge nhánh `ha_vang` mang vào `develop` nhiều thứ chỉ phục vụ một khách. Đợt này gỡ
chúng đi, đồng thời sửa một lỗi tiền phát hiện trong lúc kiểm thử.

| Nhóm | Nội dung |
|---|---|
| Sửa lỗi | Phiếu trả POS ghi nhận hoàn **thiếu đúng phần thuế** |
| Gỡ đặc thù | Mẫu in đổi tên `POS Ha Vang Receipt` → `POS Retail Receipt` |
| Gỡ đặc thù | Chính sách "miễn đổi trả", giờ mở cửa, nhãn ca — chuyển sang cấu hình POS Profile |
| Khôi phục | Mẫu in lõi `POS Next Receipt`, 3 custom field Sepay, tài liệu VNPost |
| Tuỳ chọn hoá | Hạch toán VAS + bút toán ví, gate bằng cờ trên Company (mặc định TẮT) |
| Hạ tầng | Fixtures Custom Field lọc theo `module` thay vì danh sách tên |

## Điều kiện chuẩn bị

- **Môi trường:** develop — `http://mbw.com:8040` (bench `test_core`)
  - Đã chạy `bench --site mbw.com migrate` và `yarn build` trong `apps/pos_next/POS`
- **Tài khoản:** `administrator` / `<hỏi team>`
- **Cách vào tính năng:**
  - **POS:** mở trình duyệt → `http://mbw.com:8040/pos` → chọn cửa hàng `POS Hà Nội`
  - **Mẫu in:** Sidebar → gõ `Print Format` vào ô tìm kiếm → mở danh sách
  - **Cấu hình cửa hàng:** Sidebar → tìm `POS Profile` → mở `POS Hà Nội`
  - **Cờ hạch toán:** Sidebar → tìm `Company` → mở `MBW Digital` → mục **POS Next — Hạch toán**
- **Dữ liệu cần có** (đã có sẵn trên site, ghi đúng mã để người sau lấy trùng):
  - POS Profile `POS Hà Nội` — công ty `MBW Digital`, kho `Kho Hà Nội - MBWD`
  - Khách hàng `Aha Coffee Thụy Khuê` (mã `HRC-HN-010`)
  - Hàng `Bia Hà Nội 330ml` (`FMCG-BEV-0010`) — 480.000/thùng, **thuế 10%**
  - Hàng `Bánh quy Cabiso` (`BANHᴄᴀʙɪꜱᴏ001`) — 25.000/hộp, thuế 0%
  - Hàng `Bánh quy Cosy Marie` (`FMCG-SNCK-024`) — 720.000/thùng
  - Ca POS đang mở trên `POS Hà Nội`
- **Dữ liệu tự tạo cho test:** có — xem cột "Dữ liệu vào". Đều đặt tiền tố `QATEST` / `zz-`
  và đã dọn sạch sau vòng chạy của Claude.

⚠ **Đọc trước khi chạy:** cột "KQ thực tế" là kết quả **vòng một do Claude chạy**, không
phải kết luận nghiệm thu. Người test chạy lại bằng tay rồi mới chốt Pass/Fail.

---

## Bảng test case

### TC-HAPPY — luồng đúng

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-HAPPY-01 | Bán hàng bình thường vẫn chạy | 1. Mở POS `POS Hà Nội`<br>2. Bấm chọn 2 mặt hàng<br>3. Chọn khách<br>4. Bấm **Checkout**<br>5. Bấm ô số tiền gợi ý<br>6. Bấm **Complete Payment** | Bánh quy Cabiso ×1, Bia Hà Nội ×1, khách Aha Coffee Thụy Khuê | Hiện "Invoice Created Successfully" kèm mã hoá đơn; Tổng cộng 505.000 + thuế 48.000 = **553.000**; tồn kho giảm ngay trên lưới hàng | Pass — tạo `ACC-SINV-2026-00102`, tồn 10→9 và 888→887 | P |
| TC-HAPPY-02 | In hoá đơn lấy đúng mẫu của cửa hàng | Sau TC-HAPPY-01, bấm **Print Invoice** | — | Mở tab in với mẫu **`POS Retail Receipt`** (mẫu khai ở POS Profile), không phải mẫu nào khác | Pass — URL in chứa `format=POS Retail Receipt` | P |
| TC-HAPPY-03 | Mẫu in lõi `POS Next Receipt` render được | Mở `http://mbw.com:8040/printview?doctype=Sales Invoice&name=<mã hoá đơn>&format=POS Next Receipt&no_letterhead=1` | Hoá đơn ở TC-HAPPY-01 | Ra phiếu "PHIẾU TÍNH TIỀN", số tiền khớp hoá đơn, **không** báo lỗi | Pass — trước khi sửa mẫu này lỗi `PrintFormatError: 'receipt_logo_url_for_print' is undefined` | P |
| TC-HAPPY-04 | Trả hàng toàn phần hoàn đủ tiền | 1. Ở POS bấm **Return Invoice**<br>2. Chọn hoá đơn vừa bán<br>3. Bấm **Select All**<br>4. Kéo xuống bấm **Create Return** | Hoá đơn 553.000 | Tạo phiếu trả; **tiền hoàn = 553.000**; công nợ = **0** trên cả phiếu trả lẫn đơn gốc | Pass — `ACC-SINV-2026-00103`, payments −553.000, công nợ 0/0, bút toán lệch 0đ | P |
| TC-HAPPY-05 | Trả một phần theo dòng | Như trên nhưng chỉ tích **một** dòng hàng | Đơn 2 dòng (553.000), chỉ trả dòng Bia | Hoàn đúng 528.000; công nợ 0 hai đầu | Pass | P |
| TC-HAPPY-06 | Trả một phần theo số lượng | Đơn có số lượng 2, giảm **Return Qty** xuống 1 rồi tạo phiếu trả | Bia Hà Nội ×2 (1.056.000), trả 1 | Hoàn đúng 528.000 | Pass | P |
| TC-HAPPY-07 | Hoàn vào ví khách thay vì tiền mặt | Trong màn trả hàng, tích **Add to Customer Credit Balance** rồi tạo phiếu | Trả 1 thùng Bia (528.000) | Không hoàn tiền mặt; khách được ghi có 528.000; POS đọc ra khoản credit đó | Pass — bút toán ghi Có 131 cho khách 528.000, `get_customer_balance` trả `total_credit = 528.000` | P |

### TC-VALID — kiểm tra dữ liệu

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-VALID-01 | Bắt buộc chọn khách trước khi thanh toán | Thêm hàng vào giỏ, **không** chọn khách, bấm Checkout | — | Báo lỗi *Please select a customer before proceeding* | Pass — banner đỏ "Validation Error / Please select a customer before proceeding" | P |
| TC-VALID-02 | Tài khoản ví phải thuộc đúng công ty | Mở POS Settings, đặt **Wallet Account** là tài khoản của công ty khác rồi Lưu | Tài khoản 131 của công ty B, POS Profile thuộc công ty A | Chặn lưu, báo rõ tài khoản thuộc công ty nào và POS Profile thuộc công ty nào | **Cần người test** — Claude chưa chạy case này; logic nằm ở `POSSettings.validate_wallet_account_company()` | — |

### TC-EDGE — biên & lặp

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-EDGE-01 | **Trả đơn có chiết khấu bill** (ca sinh lệch làm tròn) | 1. Tạo POS Coupon giảm 15% trên tổng đơn<br>2. Bán 3 dòng, áp coupon, thanh toán<br>3. Trả toàn phần | Cabiso + Bia + Cosy Marie, coupon `QATEST15` 15% | Màn trả hàng cộng theo dòng ra **1.089.250,01** trong khi tổng đơn là **1.089.250,00**; hệ thống hấp thụ 0,01đ, lưu 1.089.250,00, công nợ **0** hai đầu | Pass — đúng như mô tả; đây là nhánh `NGUONG_LECH_LAM_TRON = 10` trong `overrides/sales_invoice.py` | P |
| TC-EDGE-02 | Cửa hàng **chưa khai** chính sách / giờ mở cửa | Để trống *Terms and Conditions* và *Giờ mở cửa* trên POS Profile rồi in phiếu | POS Profile trống 2 ô đó | Phiếu **không in** dòng "Giờ mở cửa" và **không in** đoạn chính sách | Pass | P |
| TC-EDGE-03 | Cửa hàng **đã khai** chính sách / giờ mở cửa | Khai *Giờ mở cửa* = `9h00 - 22h00`, gán một *Terms and Conditions* rồi in phiếu | Terms chứa HTML (`<p>`, `<b>`) | In đủ cả hai dòng; đoạn chính sách ra **chữ thuần**, không lòi thẻ `<p>` / `<b>` ra giấy | Pass — đã kiểm cả HTML lẫn dữ liệu API in nhiệt | P |
| TC-EDGE-04 | Nhãn ca phản ánh ca thật | In phiếu của hoá đơn thuộc ca đầu tiên trong ngày | — | In `Ca: Ca 1`. Ca thứ hai trong ngày phải in `Ca 2` | Một phần — Claude xác nhận ca đầu ra `Ca 1`. **Cần người test** ca thứ hai: đóng ca rồi mở ca mới trong cùng ngày, bán 1 đơn, in phiếu, phải ra `Ca 2` | — |
| TC-EDGE-05 | Trả hàng khi đơn gốc bán không trừ kho | Chọn trả một hoá đơn được tạo không bật *Update Stock* | `ACC-SINV-2026-00040` | Báo lỗi *'Update Stock' can not be checked because items are not delivered via `<mã đơn>`* | Pass — đúng thông báo trên, phiếu trả không được tạo | P |

### TC-PERM — phân quyền

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-PERM-01 | Thu ngân **không** mở được cửa hàng ngoài quyền | Đăng nhập bằng thu ngân chỉ thuộc `POS Hà Nội`, thử mở POS Profile `ToanFarm` | User `zz-test-cashier@example.com`, role `POSNext Cashier`, chỉ có mặt trong `POS Hà Nội` | Chặn, báo *You don't have access to this POS Profile* | Pass | P |
| TC-PERM-02 | Thu ngân mở được đúng cửa hàng của mình | Cùng user trên, mở `POS Hà Nội` | — | Vào được bình thường | Pass | P |
| TC-PERM-03 | **Tầng dữ liệu** — API trả hàng có vượt quyền không | Dưới chính user bị giới hạn, gọi `get_returnable_invoices(pos_profile="ToanFarm")` rồi **so với** `frappe.get_list("Sales Invoice", filters={"pos_profile": "ToanFarm"})` chạy dưới cùng user | — | Hai con số **bằng nhau** — API không trả nhiều hơn phạm vi Frappe cho phép | Pass — API trả 5, `frappe.get_list` cũng trả 5 | P |
| TC-PERM-04 | Thu ngân không xoá được hoá đơn | Xem `custom_docperm` của role `POSNext Cashier` trên Sales Invoice | — | `delete = 0` | Pass — xác nhận trong fixtures | P |

> **Ghi chú TC-PERM-03.** Con số 5 = 5 nghĩa là *code không rò rỉ*. Nhưng nó cũng cho
> thấy role `POSNext Cashier` trên site này **được Frappe cho đọc hoá đơn của mọi cửa
> hàng** — vì chưa ai đặt User Permission theo POS Profile cho thu ngân. Đây là **cấu
> hình phân quyền của site**, không phải lỗi code, và có từ trước đợt sửa này. Nếu
> nghiệp vụ yêu cầu thu ngân chỉ thấy đơn cửa hàng mình thì phải thêm User Permission —
> nên đưa thành một việc riêng.

### TC-REGR — regression app lõi

App cùng hook các DocType đợt này đụng tới (tra bằng `grep -rn "Sales Invoice" apps/*/*/hooks.py`):
`mbwnext_advanced_selling`, `mbwnext_advanced_accounting`, `mbwnext_einvoice`.

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-REGR-01 | Đơn bán thường (không phải POS) không đổi hành vi | Tạo một Sales Invoice trên desk, submit | Đơn bất kỳ có thuế | Tổng tiền và bút toán y như trước đợt sửa; không phát sinh dòng thanh toán lạ | **Cần người test** — Claude chỉ chạy đường POS | — |
| TC-REGR-02 | Bút toán phiếu trả đảo đúng đối xứng đơn bán | So bảng bút toán của đơn bán và phiếu trả tương ứng | Cặp đơn ở TC-HAPPY-04 | Mỗi tài khoản ở phiếu trả có số **ngược dấu** đúng bằng đơn bán; tổng Nợ − Có = 0 | Pass — 1111 / 131 / 5111 / 1331 / 1561 / 6418 đều đối xứng, lệch 0,00 | P |
| TC-REGR-03 | Mẫu in lõi vẫn nằm trong danh sách chọn | Mở POS Profile → ô **Print Format** → gõ `Receipt` | — | Danh sách hiện **cả hai** `POS Next Receipt` và `POS Retail Receipt` | Pass — bộ lọc hiện là `Doc Type in Sales Invoice, POS Invoice` | P |
| TC-REGR-04 | Sepay QR còn đủ trường cấu hình | Mở POS Profile, bật *Enable Sepay*, xem 3 ô Bank Code / Account Holder / Bank Account Number | — | Cả 3 ô đều tồn tại và nhập được | Pass — đã khôi phục 3 custom field; trước đó nhánh `ha_vang` xoá mất trong khi `api/sepay.py` vẫn đọc | P |
| TC-REGR-05 | Hạch toán mặc định **không** đổi | Mở hồ sơ Công ty → mục **POS Next — Hạch toán** | Công ty `MBW Digital` | Cả 2 cờ đang **TẮT**, tức giữ nguyên cách hạch toán gốc | Pass — kiểm cả trên DB lẫn giao diện | P |
| TC-REGR-06 | Bật cờ ví thì mới bỏ bút toán tích điểm | Bật cờ *Không ghi sổ khi tích điểm ví* rồi tạo phiếu tích điểm; tắt cờ rồi tạo lại | Wallet Transaction loại `Loyalty Credit` | Cờ TẮT → sinh 2 bút toán, huỷ thì đảo hết; cờ BẬT → 0 bút toán | Pass — chạy trên bench, có rollback | P |

### TC-ISO — cách ly

| Mã | Mục tiêu | Bước thực hiện | Dữ liệu vào | Kết quả mong đợi | KQ thực tế | P/F |
|---|---|---|---|---|---|---|
| TC-ISO-01 | Custom Field khai đúng module | `SELECT module, COUNT(*) FROM tabCustom Field WHERE module='POS Next'` | — | Đúng **75** bản ghi, khớp số dòng trong `fixtures/custom_field.json` | Pass | P |
| TC-ISO-02 | **Export fixtures không làm mất field** | Chạy `bench --site mbw.com export-fixtures --app pos_next` rồi so file trước/sau | — | Số field **không đổi**, không field nào biến mất | Pass — 75 → 75. ⚠ Trước khi sửa `hooks.py`, lệnh này chỉ giữ **12** field và xoá 63 field còn lại | P |
| TC-ISO-03 | App lõi khác không bị đụng | `cd apps/mbwnext_advanced_selling && git status` (làm tương tự cho các app lõi khác) | — | Working tree sạch | **Cần người test** — Claude chỉ kiểm trong `pos_next` | — |
| TC-ISO-04 | Site chưa từng cài vẫn cài được | Dựng site sạch, cài `pos_next`, kiểm 5 custom field mẫu in và 2 mẫu in có được tạo không | Site mới | Có đủ `custom_shop_code`, `custom_store_name_2`, `custom_address`, `custom_phone`, `custom_store_hours` và 2 Print Format | **Cần người test** — chưa dựng site sạch. Đây là case **quan trọng nhất còn lại**, vì nó kiểm đúng thứ mà nhánh `ha_vang` đã làm hỏng | — |

### TC-PWA

Không áp dụng — đợt này không đụng tới màn hình mobile / service worker.

---

## Việc phải làm tay trên site Hạ Vàng sau khi triển khai

Đợt này gỡ nội dung gắn cứng khỏi mẫu in, nên phiếu của Hạ Vàng **sẽ mất chính sách và
giờ mở cửa** cho tới khi khai lại:

1. Tạo một **Terms and Conditions** chứa câu *"Hàng mua rồi miễn đổi trả, xem chi tiết
   bảo hành tại cửa hàng."* rồi gán vào ô **Terms and Conditions** của từng POS Profile.
2. Điền ô **Giờ mở cửa** = `9h00 - 22h00` trên từng POS Profile.
3. Nếu muốn giữ cách hạch toán cũ, bật 2 cờ trong hồ sơ Công ty:
   *Tách thuế GTGT khỏi khuyến mại (VAS)* và *Không ghi sổ khi tích điểm ví*.
   Bật cờ ví **sau khi** đã migrate thì phải chạy tay:
   ```bash
   bench --site <site> execute pos_next.patches.v1_14_1.bo_but_toan_tich_diem.execute
   ```

## Lỗi dữ liệu của site dev (không phải lỗi code, đừng ghi Fail)

- Ảnh hàng hoá thiếu file → `/files/19.png`, `/files/3.png` trả HTTP 500 trên lưới hàng.
- Địa chỉ công ty có mã bưu chính rác → phiếu in hiện chữ **NaN** ở khối địa chỉ.
- Item Tax Template trỏ vào **1331** (thuế GTGT được khấu trừ) thay vì **33311** (thuế
  đầu ra) → đơn bán ghi thuế vào tài khoản đầu vào. Cấu hình kế toán của site.

## Kết luận

- Tổng: **26** — Pass: **20** — Fail: **0** — Cần người test: **6**
- Lỗi còn lại: không có lỗi nào phát hiện chưa sửa trong phạm vi đợt này.
- Đủ điều kiện nghiệm thu: **chưa** — còn 6 case cần chạy tay, trong đó
  **TC-ISO-04 (cài site sạch)** là case bắt buộc phải chạy trước khi triển khai,
  vì nó kiểm đúng loại lỗi mà nhánh `ha_vang` đã gây ra.

### Dọn dẹp sau vòng chạy của Claude

Đã dọn sạch, site trả về nguyên trạng:

- Huỷ 18 chứng từ test (`ACC-SINV-2026-00090` → `00107`) — 0 bút toán còn sống
- Xoá coupon `QATEST15`, Terms and Conditions `QA Test Policy`
- Xoá user `zz-test-cashier@example.com` và gỡ khỏi POS Profile
- Trả 4 POS Profile về `custom_store_hours = NULL`, `tc_name = NULL`
- Tồn kho về đúng số ban đầu: Cabiso 10, Bia Hà Nội 888, Cosy Marie 967
