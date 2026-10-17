# Đổi trả hàng trên POS

**Khách hàng:** dùng chung cho mọi khách chạy POS Next (không riêng khách nào)
**Người yêu cầu:** anh Thắng (thangdo@mbw.vn)
**Người trực tiếp thao tác đã trao đổi:** *chưa có — cần hỏi thu ngân của ít nhất 1 khách đang chạy POS*
**Ngày phân tích:** 2026-09-24
**PM Project:** PM-PRJ-00025 · **PM Feature:** PM-FEAT-00060
**Tầng dự kiến:** tầng 3 — `pos_next`. Phần nào chỉ một khách cần thì tách xuống app khách sau.

> ⚠ Đây là **bản phân tích của Claude**, không phải lời khách. Mục "Hiện trạng" được đọc từ code
> `pos_next` nhánh `ha_vang` (HEAD `ead6e50`, 2026-09-08) trên bench `mbwnext_account_ha`. Các nhánh
> `develop` / `vnpost` là bản cũ hơn và có thể khác.

## Đầu bài gốc (nguyên văn)

> Anh muốn làm 1 tính năng đổi trả hàng trên POS có thể đáp ứng được cho nhiều khách hàng và cho
> nhiều loại trường hợp xảy ra nhất có thể mà vẫn đảm bảo đúng về tiền, hãy đưa ra cho anh các case
> có thể xảy ra cũng như cách xử lý từng case để thiết kế nhé
> — PM-FEAT-00060, anh Thắng

---

## 0. Đã chốt — 2026-09-29

Anh Thắng chốt qua hai kênh:
- Trang chốt https://claude.ai/artifact/8cnHdiN3T2DoqAC71d7ecv (tối 24/9): 9/9 câu, 61/65 case.
- Bình luận trên PM-FEAT-00060 (22:23 ngày 24/9 và 08:54 ngày 29/9).

Chỗ nào bảng này khác mục 3 ở dưới thì **bảng này thắng**. Mục 3 giữ nguyên làm bản phân tích gốc.

| Chủ đề | Chốt |
|---|---|
| Số lần đổi trả | **Mỗi hóa đơn chỉ được đổi trả 1 lần** (A3). Đổi xong thì hóa đơn mới làm gốc cho lần sau (B7) |
| Phạm vi hóa đơn | Chỉ trả **đúng hóa đơn, đúng cửa hàng**: không trả không hóa đơn (A4), không chéo cửa hàng (A5), không trả đơn online (A10) |
| Quá hạn | **Chặn cứng**, không ai duyệt vượt (A6) |
| Kỳ đã khóa sổ | **Không cho trả** (A8) |
| Quản lý duyệt | **Không làm** (H1) |
| Hóa đơn còn nợ | **Giảm nợ trước**, dư mới hoàn tiền (D7) |
| Đổi sang hàng rẻ hơn | **Mỗi khách tự cấu hình**: hoàn tiền / ghi có / bắt lấy thêm (B3) |
| Hàng mới hết tồn | **Không cho đổi** (B6) |
| Cách hoàn tiền | **Giữ như hiện tại**, thu ngân chọn tự do (D2, D3, D4) |
| Điểm đã tiêu | **Quy điểm ra tiền, trừ vào tiền hoàn** (E2) |
| Quà tặng kèm | **Chặn**, phải trả kèm quà (C5) |
| Combo | **Cho trả lẻ**, tính theo **giá lúc mua**: hoàn = giá combo đã trả − giá bán lẻ lúc mua của các món giữ lại. Ra ≤ 0 thì hoàn 0đ (**đề xuất của em, chờ anh Thắng xem trên mockup**) (C8) |
| Đơn vị tính | Chỉ trả **đúng đơn vị gốc**. Hàng cân được trả số lẻ, hàng khác chỉ trả số nguyên (F3, F4) |
| Hàng ngừng kinh doanh | **Không cho trả** (F6). Lỗi số 9 ở mục 5 vì vậy **không phải lỗi** |
| Hàng dịch vụ | **Không hoàn** (F7) |
| Hóa đơn điện tử | **Làm giai đoạn sau** (G1, G4). Riêng G2 (loại phiếu trả khỏi bảng kê cuối ngày) em đề xuất sửa ở đợt 1 vì đang là lỗi; anh Thắng chưa phản hồi điểm này |
| Chia đợt | **Đồng ý 2 đợt** (xem mục 6) |
| Khảo sát quầy | Hỏi thu ngân **Hạ Vàng**, chưa có đầu mối |

---

## 1. Hệ thống đang làm được gì

| Hạng mục | Hiện trạng |
|---|---|
| Trả hàng có hóa đơn gốc | ✅ Có. Tạo Sales Invoice `is_return=1`, trả được một phần, trả nhiều lần. Tìm hóa đơn theo số HĐ / tên / SĐT trong 50 HĐ gần nhất cùng POS Profile |
| Trả hàng không hóa đơn | ❌ Có cài đặt `allow_return_without_invoice` nhưng không có màn hình |
| **Đổi hàng** | ❌ **Chưa có.** Hiện phải làm 2 bước: trả hàng rồi ghi có cho khách, sau đó bán đơn mới và thanh toán bằng "Customer Credit" |
| Hạn đổi trả | ✅ `return_validity_days` được kiểm ở server |
| Bật/tắt trả hàng (`allow_return`) | ❌ Có cài đặt nhưng không có tác dụng: nút vẫn hiện, server không kiểm |
| Quản lý duyệt / nhập PIN | ❌ Không có |
| Hoàn tiền | ✅ Hoàn theo phương thức của HĐ gốc, không vượt số đã trả. Có ghi vào số dư khách, trả vào ví, và giảm công nợ với HĐ bán nợ |
| Hàng tặng kèm | ✅ Bắt trả kèm hàng chính. Hàng tặng hoàn 0đ |
| Thu hồi KM ngưỡng đơn | ⚠ Có, nhưng khả năng **trừ trùng** (xem mục 5) |
| Điểm tích lũy | ⚠ ERPNext tính lại điểm. Điểm **đã đổi sang ví thì không thu hồi** |
| Coupon | ❌ Không trả lại lượt dùng |
| Lô / serial | ⚠ Dựa vào ERPNext tự dựng lại từ dòng gốc. **Chưa test** |
| Hàng cân (kg) | ❌ Ô số lượng chỉ nhận số nguyên, bước 1 |
| Hàng ngừng kinh doanh | ❌ `mbwnext_advanced_selling` chặn luôn cả phiếu trả |
| Hóa đơn điện tử | ❌ Chưa xử lý phiếu trả. Phiếu trả âm còn có thể lọt vào bảng kê HĐĐT cuối ngày |
| Offline | ❌ Chặn, chỉ làm được khi online (hợp lý, nên giữ) |

### 1.1 Đối chiếu nhánh `develop` (2026-10-01)

Mục 1 và mục 5 ban đầu đọc từ nhánh `ha_vang`. Em đã đối chiếu lại với `develop` (`9263e4b`, 27/08) vì tính
năng làm trên nhánh này. Hai nhánh chỉ lệch 4 commit (chỉ ở `ha_vang`) và 10 commit (chỉ ở `develop`).
Phần trả hàng gần như **giống hệt**: các hàm trong `invoices.py` ở đúng số dòng đã ghi, chỉ có 3 khác biệt:

| # | Khác biệt | Ảnh hưởng tới đổi hàng |
|---|---|---|
| 1 | **`develop` chưa có PM-TASK-00186** (`ReturnInvoiceDialog.vue`): ô "Add to Customer Credit Balance" vẫn hiện kể cả khi cửa hàng không bật bán chịu / dùng số dư khách. Hạ Vàng đã sửa ở `ha_vang` bằng `canUseCustomerCredit` | **Chọn "Ghi có" ở B3 mà số dư không tiêu được thì khách mất tiền.** Dialog đổi hàng phải mang theo điều kiện này (chỉ cho chọn ghi có khi `allowCreditSale` hoặc `allowCustomerCreditPayment` bật). Khi đưa `feat/doi-hang` sang `ha_vang` sẽ **xung đột ở file này**, vì đổi hàng viết lại dialog, nên cần gộp tay |
| 2 | **Hạch toán tách thuế khỏi khuyến mại (VAS) trên `develop` mặc định tắt**: chỉ chạy khi công ty bật `Company.pos_next_tach_thue_khuyen_mai`. `ha_vang` thì chạy luôn | Muốn thử bút toán khuyến mại như Hạ Vàng (C4, D7) thì phải bật cờ này trên công ty test. Đổi hàng chia phần KM giữa phiếu trả và HĐ mới nên cần test cả hai trạng thái cờ |
| 3 | `develop` đã gỡ code đặc thù Hạ Vàng, đổi tên mẫu in thành `POS Retail Receipt` (hàm `retail_receipt_meta_for_jinja`) | Phiếu đổi trả (H5) làm trên mẫu `POS Retail Receipt`, không phải `POS HA Vang Receipt` |

Phần sửa thuế phiếu trả (`2713b74` ở `ha_vang`) và PM-TASK-00136 **đã có** ở `develop` (`b97bc05`, `9263e4b`).
Các lỗi số 1 đến 8 và 10 ở mục 5 vẫn đúng trên `develop`.

---

## 2. Năm nguyên tắc để đảm bảo đúng tiền

Mọi case bên dưới đều quy về 5 nguyên tắc này. Nếu thiết kế giữ được cả 5 thì tiền luôn khớp.

1. **Hoàn theo giá khách THỰC TRẢ, không theo giá niêm yết hiện tại.**
   `Tiền hoàn 1 dòng = (đơn giá sau CK dòng − phần CK tổng đơn phân bổ cho dòng + thuế) × SL trả`
2. **Tổng hoàn lũy kế của một HĐ ≤ số khách đã trả thật.** Phần chưa trả (công nợ) thì chỉ được
   giảm nợ, không được chi tiền.
3. **Đổi hàng = một giao dịch, thanh toán phần chênh.**
   `Chênh lệch = Giá trị hàng mới (giá + KM hiện hành) − Giá trị hàng trả (theo nguyên tắc 1)`.
   Chênh > 0 thì khách trả thêm. Chênh < 0 thì hoàn tiền hoặc ghi có.
4. **Quyền lợi phát sinh từ HĐ gốc phải đánh giá lại trên phần khách GIỮ LẠI.** Gồm KM ngưỡng đơn,
   quà tặng, điểm, coupon. Phần giữ lại không còn đủ điều kiện thì thu hồi phần chênh.
5. **Tiền hoàn đi ngược kênh đã thu, trong giới hạn từng kênh.** Kênh nào không hoàn ngược được
   (thẻ, ví điện tử) thì phải có quy tắc thay thế rõ ràng và có ghi lại.

---

## 3. Các case và cách xử lý

Cột **HT** là hiện trạng: ✅ có · ⚠ có một phần hoặc có lỗi · ❌ chưa có.

### A. Chứng từ gốc

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| A1 | Trả **toàn bộ** HĐ | Phiếu trả gắn `return_against`. Hoàn đúng số đã trả, gồm cả phần thu hồi KM | ✅ |
| A2 | Trả **một phần** số lượng / một phần dòng | Tính theo nguyên tắc 1 và 4 | ✅ |
| A3 | Trả **nhiều lần** trên cùng HĐ | Theo dõi SL đã trả **theo từng dòng gốc** (`sales_invoice_item`), không theo mã hàng. Lần sau chỉ trả được phần còn lại | ⚠ server đếm theo mã hàng, màn hình đếm theo dòng. Nút Trả ở Lịch sử HĐ mất sau lần trả đầu |
| A4 | **Không có hóa đơn** (mất bill) | Bước 1: tra theo SĐT khách, serial hoặc lô để tìm lại HĐ. Không tìm được thì: lấy giá = **giá bán thấp nhất của mã đó trong N ngày** (hoặc giá hiện hành, tùy khách cấu hình). **Bắt quản lý duyệt.** Chỉ hoàn bằng **ghi có / phiếu mua hàng**, không chi tiền mặt | ❌ |
| A5 | HĐ mua ở **cửa hàng / POS Profile khác** cùng công ty | Cấu hình: cho phép hay không. Cho phép thì hàng nhập về kho của cửa hàng đang trả, còn tiền chi từ ca đang mở | ❌ hiện chặn khác POS Profile |
| A6 | **Quá hạn** đổi trả | Chặn. Cho quản lý duyệt vượt, và ghi lý do | ⚠ chặn cứng, không có duyệt vượt |
| A7 | HĐ gốc thuộc **ca / ngày trước** | Phiếu trả ghi vào **ca hiện tại**. Không sửa ca cũ | ✅ |
| A8 | HĐ gốc thuộc **kỳ kế toán đã khóa sổ** | Phiếu trả hạch toán ngày hiện tại, **không** hạch toán lùi ngày HĐ gốc | cần kiểm |
| A9 | HĐ gốc là **HĐ bán nợ / trả góp một phần** | Xem D6, D7 | ✅ |
| A10 | Trả hàng từ **đơn online / đơn giao hàng** (không phải HĐ POS) | Ngoài phạm vi lần này, trừ khi anh muốn gộp. Cần chốt | ❌ |

### B. Loại đổi hàng (tính năng mới)

| # | Case | Cách xử lý đề xuất |
|---|---|---|
| B1 | Đổi **cùng mã, khác size / màu** (biến thể), cùng giá | Chênh 0đ. Vẫn tạo phiếu trả và HĐ mới để tồn kho đúng theo biến thể |
| B2 | Đổi sang hàng **đắt hơn** | Khách trả thêm phần chênh bằng bất kỳ phương thức nào |
| B3 | Đổi sang hàng **rẻ hơn** | Cấu hình theo khách: (a) hoàn tiền, (b) chỉ ghi có / phiếu mua hàng, (c) bắt mua thêm cho đủ giá trị. Mặc định đề xuất là (b) |
| B4 | Đổi **1 lấy nhiều** / **nhiều lấy 1** / nhiều lấy nhiều | Cùng một màn hình: danh sách "Hàng trả" và danh sách "Hàng lấy mới". Chỉ thanh toán tổng chênh |
| B5 | Đổi hàng **lỗi** lấy hàng cùng loại (bảo hành đổi mới) | Hàng trả nhập vào **kho hàng lỗi** (cấu hình theo POS Profile), không cộng vào tồn bán. Chênh 0đ. Bắt chọn lý do "lỗi" |
| B6 | Hàng muốn đổi **hết tồn** | Không chặn phần trả. Ghi có cho khách, hoặc tạo đơn đặt hàng. Không cho HĐ mới xuất âm kho |
| B7 | Đổi **nhiều lần nối tiếp** (A đổi sang B, rồi B đổi sang C) | Lần sau lấy HĐ mới (B) làm gốc. Giá trị hoàn theo giá đã dùng khi đổi lần trước, không theo giá lần mua đầu |
| B8 | Hàng mới đang có **KM khác** lúc mua | Hàng mới áp KM **hiện hành**. Hàng trả tính theo giá **lúc mua**. Hai bên độc lập |
| B9 | Khách đổi rồi **hủy đổi** ngay tại quầy | Chưa bấm hoàn tất thì chưa tạo chứng từ nào. Đã hoàn tất thì phải làm một lần đổi ngược lại, không cho hủy chứng từ ngay |

**Cách làm đề xuất cho đổi hàng:** **một màn hình, một nút hoàn tất, sinh ra 2 chứng từ liên kết
với nhau**:
- Phiếu trả (SI `is_return=1`) và HĐ mới (SI thường).
- Hai chứng từ nối với nhau bằng trường `exchange_ref`.
- Giá trị phiếu trả được **phân bổ thẳng làm thanh toán** cho HĐ mới. Cơ chế này đã có sẵn: Customer
  Credit / Journal Entry.
- Chỉ phần chênh đi qua quỹ.
- Chạy trong **một transaction**: bước sau lỗi thì rollback cả hai, để không có trường hợp trả xong
  mà không có HĐ mới.

Không gộp thành một SI có cả dòng âm lẫn dòng dương. ERPNext v15 không hỗ trợ sạch cách này: dính
lỗi return_against, lô/serial và HĐĐT.

### C. Khuyến mãi và chiết khấu (chỗ dễ sai tiền nhất)

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| C1 | CK **theo dòng** (% hoặc số tiền) | Hoàn theo đơn giá sau CK | ✅ |
| C2 | CK **tổng đơn** | Phân bổ theo tỷ lệ giá trị từng dòng. Hoàn = phần của dòng trả | ✅ |
| C3 | KM **ngưỡng đơn** (đơn ≥ X được giảm Y). Phần giữ lại **vẫn ≥ X** | Không thu hồi. Hoàn theo C2 | ✅ |
| C4 | KM ngưỡng đơn, phần giữ lại **< X** | Thu hồi. **Công thức đề xuất:** Hoàn = Giá trị hàng trả tính theo giá **trước** CK tổng đơn − toàn bộ Y đã giảm + phần Y đã phân bổ cho hàng giữ lại, tức **khách mất đúng Y, không hơn không kém**. Ví dụ ở dưới | ⚠ nghi trừ trùng |
| C5 | **Mua X tặng Y**, trả X, **giữ Y** | Trừ giá trị Y (giá vốn hoặc giá bán, cấu hình theo khách) vào tiền hoàn, hoặc bắt trả kèm Y | ✅ bắt trả kèm |
| C6 | Mua X tặng Y, **chỉ trả Y** | Hoàn 0đ. Chỉ nhập kho | ✅ |
| C7 | **Bậc thang số lượng** (mua 3 được giá rẻ hơn), trả 1 | Tính lại giá cho số lượng giữ lại theo bậc đúng. Hoàn = Đã trả − Giá trị phần giữ lại tính lại | ❌ |
| C8 | **Combo / bộ** giá trọn gói, trả 1 món trong combo | Mặc định chỉ cho trả nguyên combo. Nếu cho trả lẻ thì hoàn = giá combo × tỷ trọng giá lẻ của món đó | ❌ |
| C9 | **Coupon / voucher** giảm giá | Trả toàn bộ HĐ: hoàn lại lượt dùng coupon (nếu coupon còn hạn). Trả một phần: coupon coi như CK tổng đơn (C2 / C4) | ❌ |
| C10 | **Phiếu quà tặng / thẻ quà** khách dùng để thanh toán | Coi như một phương thức thanh toán. Hoàn về thẻ quà, không hoàn tiền mặt | cần chốt |

**Ví dụ C4 (thu hồi KM ngưỡng đơn):** Đơn gồm A 300k + B 200k = 500k, KM "đơn ≥ 400k giảm 50k", khách
trả 450k. Phân bổ giảm giá: A −30k, B −20k. Khách trả B.
- Nếu **không** thu hồi KM: hoàn 180k (200k − 20k).
- Phần giữ lại 300k < 400k nên KM mất hiệu lực. Khách lẽ ra chỉ trả 300k cho A, nhưng đã trả 450k,
  vậy **hoàn đúng = 150k**. Kiểm lại: 180k − 30k (phần giảm của A bị thu hồi) = 150k.
- **Sai hay gặp:** lấy 180k trừ nguyên 50k thành 130k, là trừ trùng 20k. Code hiện tại nghi đang
  mắc lỗi này.

### D. Thanh toán và hoàn tiền

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| D1 | Đã trả **tiền mặt** | Chi tiền mặt từ ca đang mở | ✅ |
| D2 | Đã trả **chuyển khoản / QR** | Mặc định hoàn chuyển khoản, ghi lại số TK nhận. Cho đổi sang tiền mặt nếu khách cấu hình cho phép | ⚠ cho chọn tự do |
| D3 | Đã trả **thẻ (POS ngân hàng)** | Hoàn qua máy POS (void / refund) trong ngày. Qua ngày thì hoàn chuyển khoản. Ghi mã giao dịch hoàn | ⚠ |
| D4 | Thanh toán **hỗn hợp** (tiền mặt + CK + ví) | Thứ tự hoàn đề xuất: **ví / điểm → ghi có → CK → tiền mặt**. Không kênh nào vượt số đã thu qua kênh đó | ⚠ có giới hạn từng kênh, chưa có thứ tự mặc định |
| D5 | Đã trả bằng **ví / điểm đổi tiền** | Hoàn về ví | ✅ |
| D6 | HĐ **bán nợ**, chưa trả đồng nào | Không chi tiền. Chỉ giảm công nợ | ✅ |
| D7 | HĐ **trả một phần**, còn nợ | **Đề xuất giảm nợ trước, dư mới hoàn tiền.** Ví dụ: HĐ 1tr, đã trả 400k, nợ 600k, khách trả hàng trị giá 700k thì giảm nợ 600k và hoàn 100k. Code hiện tại hoàn theo tỷ lệ: chi 280k (400k × 70%), giảm nợ 420k, khách còn nợ 180k. **Tổng tiền cả hai cách đều đúng** (khách trả ròng 300k cho hàng giữ lại), nhưng cách tỷ lệ **chi tiền mặt ra trong khi khách vẫn còn nợ**, nên rủi ro thu hồi nợ cao hơn. Cần anh chốt | ⚠ |
| D8 | Khách chọn **ghi vào số dư** thay vì nhận tiền | Tạo ghi có, dùng cho lần mua sau | ✅ |
| D9 | **Quỹ ca không đủ** tiền mặt để hoàn | Chặn, báo số quỹ hiện có. Gợi ý CK hoặc ghi có | ❌ |
| D10 | HĐ có **đặt cọc** / thanh toán trước | Hoàn theo phần đã thu thật, gồm cả tiền cọc | cần kiểm |
| D11 | **Làm tròn** tiền lẻ (hàng trăm đồng) | Hoàn theo số đã làm tròn lúc bán. Chênh ≤ 10đ đẩy vào phương thức mặc định | ✅ |

### E. Điểm tích lũy và hạng thành viên

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| E1 | HĐ gốc đã **cộng điểm** | Thu hồi điểm theo tỷ lệ giá trị trả | ✅ ERPNext tự tính |
| E2 | Điểm đó **đã tiêu / đã đổi sang ví** | Cấu hình theo khách: (a) cho điểm âm, (b) trừ quy đổi thành tiền vào số tiền hoàn. Hiện tại đang để sót, không thu hồi | ❌ |
| E3 | Khách đã **dùng điểm để thanh toán** | Hoàn lại điểm (xem D5) | ✅ |
| E4 | Trả hàng làm khách **tụt hạng** thành viên | Tính lại hạng theo doanh số ròng. Không thu hồi quyền lợi đã hưởng ở các đơn trước | cần chốt |

### F. Hàng hóa và kho

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| F1 | Hàng theo **lô / hạn dùng** | Nhập lại **đúng lô đã bán**, lấy từ dòng gốc. Trả không hóa đơn thì bắt chọn lô | ⚠ chưa test |
| F2 | Hàng **serial** (điện thoại, thiết bị) | Bắt quét đúng serial đã bán. Không khớp thì chặn | ⚠ chưa test |
| F3 | Bán theo **thùng**, trả theo **lẻ** | Cho trả số lẻ theo ĐVT gốc (0,5 thùng), hoặc quy đổi ĐVT. Tiền hoàn tính theo ĐVT cơ bản | ❌ ô số lượng chỉ nhận số nguyên |
| F4 | Hàng **cân (kg)** | Cho số lẻ theo `must_be_whole_number` của ĐVT | ❌ |
| F5 | Hàng **lỗi / hỏng** | Nhập vào kho hàng lỗi, bắt chọn lý do | ❌ |
| F6 | Hàng **đã ngừng kinh doanh** | Vẫn cho **trả**, chỉ chặn **bán** | ❌ đang chặn cả phiếu trả |
| F7 | Hàng **dịch vụ / không quản kho** (phí giao hàng, gói bảo hành) | Cấu hình từng mã có được hoàn không. Phí giao hàng mặc định không hoàn | cần chốt |
| F8 | Giá bán **đã thay đổi** từ lúc mua | Không ảnh hưởng: vẫn hoàn theo giá lúc mua (nguyên tắc 1) | ✅ |
| F9 | Trả số lượng **lớn hơn đã mua** | Chặn | ✅ |

### G. Thuế và hóa đơn điện tử

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| G1 | HĐ gốc **đã xuất HĐĐT** | Phát hành **HĐĐT điều chỉnh giảm** (hoặc theo quy định mới nhất, **kế toán cần xác nhận**). Client VNPT / MISA đã có hàm điều chỉnh nhưng chưa có nơi nào gọi | ❌ |
| G2 | HĐ gốc **chưa xuất**, gom vào bảng kê cuối ngày | Loại phiếu trả khỏi bảng kê. Trừ giá trị trả vào dòng hàng tương ứng trước khi xuất | ❌ hiện phiếu trả âm có thể lọt vào bảng kê |
| G3 | **Thuế suất đã đổi** (vd. giảm VAT 10% xuống 8%) giữa lúc mua và lúc trả | Dùng **thuế suất lúc bán** | ✅ lấy từ HĐ gốc |
| G4 | Đổi hàng | Hàng mới xuất HĐĐT mới như bán thường. Phần trả xử lý theo G1 / G2 | ❌ |

### H. Kiểm soát và vận hành

| # | Case | Cách xử lý đề xuất | HT |
|---|---|---|---|
| H1 | **Quản lý duyệt** | Bắt nhập PIN quản lý khi: không có HĐ, quá hạn, hoàn tiền mặt > ngưỡng, hoặc hoàn khác kênh gốc | ❌ |
| H2 | **Lý do trả** | Danh mục lý do (lỗi, không vừa, đổi ý…), bắt buộc chọn. Lý do quyết định kho nhận hàng | ❌ |
| H3 | **Bật / tắt** trả hàng theo POS Profile | Làm cho `allow_return` có tác dụng thật: ẩn nút và kiểm ở server | ❌ |
| H4 | Thu ngân **làm nhầm** phiếu trả | Cho hủy (cancel) trong ca, có quyền. Sau khi đóng ca thì phải làm phiếu ngược lại | cần kiểm |
| H5 | **In phiếu** đổi trả cho khách ký | Mẫu in riêng: HĐ gốc, hàng trả, hàng mới, chênh lệch, phương thức hoàn | ⚠ |
| H6 | **Báo cáo** | Đổi trả theo ca / thu ngân / lý do / mã hàng. Tỷ lệ trả theo nhân viên để phát hiện gian lận | ⚠ ca có tổng trả |
| H7 | **Mất mạng** | Giữ như hiện tại: chỉ cho làm online | ✅ |
| H8 | Hai quầy **cùng trả một HĐ** cùng lúc | Khóa HĐ gốc khi lập phiếu trả. Server kiểm lại SL còn trả được lúc submit | ⚠ |

---

## 4. Những điểm cần anh chốt (đã chốt, xem mục 0)

1. **D7:** HĐ còn nợ thì giảm nợ trước (em đề xuất, ít rủi ro hơn) hay hoàn theo tỷ lệ (code hiện tại)?
2. **B3:** Đổi sang hàng rẻ hơn thì mặc định hoàn tiền hay chỉ ghi có?
3. **A4:** Có làm trả hàng không hóa đơn không? Nếu có thì lấy giá nào?
4. **A5:** Có cho trả hoặc đổi chéo cửa hàng không?
5. **C5 / C8:** Trả hàng chính mà giữ quà, hoặc trả lẻ trong combo: chặn, hay trừ tiền theo giá vốn / giá bán?
6. **E2:** Điểm đã tiêu hết thì cho điểm âm hay trừ vào tiền hoàn?
7. **G1:** Kế toán xác nhận dùng HĐĐT điều chỉnh giảm hay HĐ trả hàng, theo từng nhà cung cấp VNPT / MISA.
8. **Phạm vi lần này:** gợi ý chia làm 2 đợt:
   - **Đợt 1:** màn hình đổi hàng (B1–B9), sửa các lỗi tiền (C4, D7, A3), duyệt quản lý và lý do (H1–H3), kho hàng lỗi (F5, F6), số lẻ (F3, F4).
   - **Đợt 2:** trả không hóa đơn (A4), bậc thang / combo (C7, C8), coupon (C9), HĐĐT (G1, G2), báo cáo (H6).
9. Cho em xin **một khách thật** để hỏi thu ngân về các ngoại lệ ở quầy (gợi ý Hạ Vàng, khách đang dùng nhánh mới nhất).

## 5. Lỗi phát hiện trong code hiện tại (nên sửa trong đợt 1)

1. **Nghi trừ trùng KM ngưỡng đơn** (C4). Đã đọc code nhưng chưa chạy thử trên đơn thật.
   - `returnTotal` tính theo `rate_with_tax = net_rate + tax_per_unit` (`invoices.py:2871`).
   - Trong ERPNext, `net_rate` đã trừ phần CK tổng đơn phân bổ cho dòng.
   - Comment ở `ReturnInvoiceDialog.vue:~1420` (develop) lại giả định "CHƯA phân bổ CK bill-level".
   - Sau đó `kmReclaimDeduction` trừ thêm **toàn bộ** CK tổng đơn.
   - Kết quả: phần CK của hàng trả bị trừ 2 lần, đúng như ví dụ C4 (ra 130k thay vì 150k).
   - Vị trí (develop `9263e4b`): `ReturnInvoiceDialog.vue` ~1381–1435 và 1486, `invoices.py` ~1590–1627 và 2848–2871.
   - Cần một đơn test có KM ngưỡng để xác nhận.
2. **SL đã trả đếm lệch.** `validate_return_items` đếm theo mã hàng, còn `prepare_return_invoice` đếm
   theo dòng. Sai khi cùng một mã nằm ở nhiều dòng (ví dụ một dòng mua, một dòng tặng).
   Vị trí: `invoices.py` ~680–770 và ~2768–2846.
3. **Thuế mỗi đơn vị** tính theo mã hàng rồi chia cho SL của một dòng, nên sai khi mã hàng lặp ở
   nhiều dòng. Vị trí: `invoices.py` ~2857.
4. **Danh sách HĐ có thể trả** có thể cộng dồn sai tổng do phép join `OR`.
   Vị trí: `invoices.py` ~2061–2074 và ~2155–2168.
5. **Nút Trả hàng biến mất trong Lịch sử HĐ** sau lần trả một phần đầu tiên (trạng thái
   "Credit Note Issued"). Vị trí: `InvoiceHistoryDialog.vue:326`.
6. **`search_invoices_for_return` lộ dữ liệu.** Hàm được whitelist, không lọc POS Profile, không kiểm
   quyền, và không nơi nào dùng. Nên xóa hoặc thêm kiểm quyền.
7. **`allow_return` không có tác dụng**, và `allow_free_batch_return` không có code nào dùng.
8. **Điểm đã đổi sang ví không bị thu hồi** khi trả hàng. Vị trí: `api/wallet.py:46`.
9. ~~**Hàng ngừng kinh doanh chặn luôn phiếu trả**~~ (`mbwnext_advanced_selling`, `discontinued_product.py:163`).
   **Không phải lỗi:** anh Thắng chốt hàng ngừng kinh doanh thì không cho trả (F6). Giữ nguyên.
10. **Phiếu trả âm có thể lọt vào bảng kê HĐĐT cuối ngày** (`einvoice_batch.py:40,252`).

---

## 6. Spec đợt 1 (bản nháp đi kèm mockup — 2026-09-29)

Mockup: `docs/mockups/doi-hang.html`.

### 6.1 Phạm vi đợt 1

- **Màn hình đổi hàng** (B1–B9), gộp chung dialog trả hàng hiện có.
- **Luật chặn:**
  - mỗi hóa đơn chỉ đổi trả 1 lần (A3);
  - quá hạn chặn cứng (A6);
  - hóa đơn thuộc kỳ đã khóa sổ (A8);
  - hàng mới hết tồn (B6);
  - hàng ngừng kinh doanh (F6), hàng dịch vụ (F7).
- **Tiền:**
  - sửa trừ trùng KM ngưỡng (C4, lỗi 1);
  - giảm nợ trước (D7);
  - trừ tiền quy đổi điểm đã tiêu (E2, lỗi 8);
  - combo trả lẻ theo giá lúc mua (C8);
  - chênh âm xử lý theo cấu hình (B3);
  - quỹ ca không đủ tiền (D9).
- **Kho:** hàng lỗi vào kho hàng lỗi theo lý do trả (F5, H2). Hàng cân được trả số lẻ (F4).
- **Kiểm soát:**
  - `allow_return` có tác dụng thật (H3, lỗi 7);
  - hủy phiếu trong ca (H4);
  - in phiếu đổi trả (H5);
  - khóa hóa đơn gốc khi đang lập phiếu (H8).
- **Lỗi đi kèm:**
  - lỗi 3 (thuế mỗi đơn vị), lỗi 4 (tổng danh sách HĐ);
  - lỗi 6 (xóa `search_invoices_for_return`);
  - lỗi 10 / G2 (loại phiếu trả khỏi bảng kê HĐĐT). G2 chờ anh Thắng đồng ý.
- **Đợt 2:** C7 (bậc thang), C9 (coupon), G1 và G4 (HĐĐT điều chỉnh), H6 (báo cáo).

Lỗi 2 và lỗi 5 tự hết khi áp luật "đổi trả 1 lần", nên không cần sửa riêng.

### 6.2 ⚠ Điểm mới cần anh Thắng chốt: tính tiền đổi hàng theo giỏ gộp

Nếu tính "trả" và "mua mới" như hai giao dịch riêng, khách **đổi size cùng giá vẫn bị mất KM
ngưỡng đơn**.

Ví dụ: HĐ gồm áo 2 × 250k + quần 450k + combo tất 99k = 1.049k. KM "đơn từ 1.000k giảm 50k", khách
đã trả 999k. Khách đổi 1 áo size M lấy size L, cùng giá.
- **Tính riêng:** trả áo làm phần giữ lại còn 799k, dưới ngưỡng nên thu hồi KM: hoàn 200k. Mua áo L
  250k, không có KM. **Khách phải bù 50k**, dù chỉ đổi size.
- **Đề xuất (tính theo giỏ gộp):**
  `Phải trả mới = giá trị (hàng giữ lại theo giá lúc mua + hàng mới theo giá hiện hành) − KM tổng đơn gốc nếu giỏ gộp vẫn đủ ngưỡng`
  `Chênh = Phải trả mới − Khách đã trả`
  Áp vào ví dụ: 799k + 250k = 1.049k, vẫn đủ ngưỡng, còn 999k. Chênh 0đ.

Các ví dụ trên mockup:

| Kịch bản | Giỏ gộp | KM | Phải trả mới | Chênh |
|---|---|---|---|---|
| Đổi áo M lấy áo L (250k) | 1.049k | −50k | 999k | **0** |
| Đổi áo lấy quần jean (450k) | 1.249k | −50k | 1.199k | **+200k** (khách trả thêm) |
| Đổi áo lấy mũ (150k) | 949k | mất KM | 949k | **−50k** (theo cấu hình B3) |
| Chỉ trả 1 áo | 799k | mất KM | 799k | **−200k** (hoàn) |

Riêng khoản **chênh âm**, cấu hình B3 quyết định cách trả:
- **Hoàn tiền:** chi cho khách.
- **Ghi có:** ghi vào số dư của khách.
- **Bắt lấy thêm:** không cho hoàn tất cho tới khi chênh ≥ 0.

Khi code, 2 chứng từ chia số tiền sao cho tổng khớp với công thức:
- Phiếu trả hoàn theo giá thực trả.
- HĐ mới nhận phần KM chuyển sang, ghi vào `discount_amount`.

### 6.3 Công thức các khoản khác

- **Combo trả lẻ (C8):**
  `hoàn = giá combo đã trả − Σ giá bán lẻ lúc mua của món giữ lại`. Ra ≤ 0 thì hoàn 0đ và báo cho thu
  ngân. Giá lẻ lúc mua lấy từ Item Price của bảng giá trên HĐ gốc, tại ngày HĐ gốc.
- **Điểm (E2):** thu hồi = điểm HĐ gốc đã cộng − điểm tính lại trên số phải trả mới. Nếu khách không
  còn đủ điểm thì phần thiếu × giá trị quy đổi 1 điểm (`conversion_factor` của Loyalty Program) được
  trừ vào tiền hoàn.
- **Hóa đơn còn nợ (D7):** khoản giảm (chênh âm) trừ vào công nợ trước. Chỉ phần vượt công nợ mới đi
  theo cấu hình B3.

### 6.4 Cấu trúc dữ liệu dự kiến (chưa tạo)

Đặt tên theo quy ước `posa_` của `pos_next`. Chưa tạo vì mockup chưa duyệt.

| Nơi | Field / DocType | Kiểu | Dùng để |
|---|---|---|---|
| Sales Invoice | `posa_is_exchange` | Check | Đánh dấu chứng từ thuộc một lần đổi hàng |
| Sales Invoice | `posa_exchange_against` | Link Sales Invoice | HĐ mới trỏ về phiếu trả của cùng lần đổi |
| Sales Invoice | `posa_return_reason` | Link POS Return Reason | Lý do trả (bắt buộc với phiếu trả) |
| **POS Return Reason** (DocType mới) | `reason_name` (Data), `stock_destination` (Select: `Sellable` / `Defective`), `disabled` (Check) | | Danh mục lý do. Lý do quyết định kho nhận hàng |
| POS Profile | `posa_defective_warehouse` | Link Warehouse | Kho hàng lỗi của cửa hàng |
| POS Settings | `exchange_negative_difference` | Select: `Refund` / `Customer Credit` / `Require Top-up` | Cấu hình B3 |
| POS Settings | `allow_return`, `return_validity_days` | có sẵn | Làm cho `allow_return` có tác dụng thật |

Quy ước đã đối chiếu trên `develop`:
- **Custom Field** (3 field Sales Invoice + 1 field POS Profile) phải khai `module = "POS Next"`. `hooks.py` lọc fixtures theo đúng module này, thiếu là field mất khi export hoặc khi cài site mới.
- `exchange_negative_difference` **không phải Custom Field**: thêm thẳng vào `pos_settings.json`, cùng chỗ với `allow_return`, `return_validity_days`.
- `POS Return Reason` là DocType riêng của app, nên khai `permissions` ngay trong file JSON: đọc cho `POSNext Cashier` (vai trò thu ngân của app), toàn quyền cho `Sales Manager` và `System Manager`. Không tự thêm `Custom DocPerm`.
- 4 lý do mặc định (Không vừa size, Lỗi sản phẩm, Khách đổi ý, Giao nhầm hàng) tạo bằng patch mới, vì thu ngân không tự thêm được.
- Điều kiện cho chọn "Ghi có" (B3) phải mang theo `canUseCustomerCredit` của PM-TASK-00186 (xem mục 1.1).

### 6.5 Lối vào

- Nút **Đổi / Trả hàng** hiện có trên màn hình bán (`POSSale.vue:128`, `InvoiceCart.vue:736`). Đổi
  nhãn từ "Trả hàng" thành "Đổi / Trả hàng".
- Nút **Đổi / Trả** trên từng dòng của Lịch sử hóa đơn (`InvoiceHistoryDialog.vue:326`). Nút ẩn khi
  HĐ đã đổi trả hoặc quá hạn.

### 6.6 Cơ chế

- API mới `pos_next.api.exchange.submit_exchange`:
  - tạo phiếu trả, rồi tạo HĐ mới, rồi phân bổ giá trị phiếu trả làm thanh toán cho HĐ mới;
  - chạy trong **một transaction**: lỗi ở bất kỳ bước nào thì rollback toàn bộ.
- Kiểm "đã đổi trả 1 lần": có Sales Invoice `docstatus=1` với `return_against = HĐ gốc` thì chặn.
  Kiểm cả ở server lúc submit, để chặn trường hợp 2 quầy cùng lập phiếu (H8).
- Kiểm kỳ khóa sổ: `posting_date` của HĐ gốc ≤ `acc_frozen_upto` (Accounts Settings), hoặc ≤ ngày
  cuối của Period Closing Voucher gần nhất, thì chặn.
- Chỉ chạy khi online (H7).

### 6.7 Ghi chú khi code phần server (2026-10-06)

API: `pos_next/api/exchange.py`, gồm `calculate_exchange` (xem trước) và `submit_exchange` (lưu).
Trả hàng thuần và đổi hàng đi chung một đường.

Phát hiện khi chạy thử trên dữ liệu thật (site dev bench 8009), đã xử lý trong code:

1. **Commit giữa chừng.** `ensure_self_service_einvoice_token` (gọi trong `submit_invoice`) tự
   `commit`. Nếu để nguyên, phiếu trả được chốt trước khi HĐ mới kịp lưu, nên HĐ mới lỗi thì phiếu
   trả vẫn còn. Đã chặn bằng cờ `frappe.flags.pos_next_dang_doi_hang`. Phiếu trả cũng không cấp mã
   tự xuất HĐĐT nữa.
2. **ERPNext tự áp KM tổng đơn cho HĐ mới.** `set_missing_values` chép `ignore_pricing_rule` từ POS
   Profile, đè giá trị gửi lên. Đã đặt lại sau bước đó (cả `update_invoice` lẫn bản tính trước), chỉ
   khi bên gọi chủ động gửi `1`. Đo thật: món mới 5 triệu tự đủ ngưỡng 10%, ERPNext giảm thêm, khách
   trả thiếu 180.100.
3. **Xóa nợ (write-off) trên phiếu trả phải là số ÂM.** Số dương làm HĐ gốc treo công nợ âm gấp đôi
   khoản thu hồi (khách được ghi có ảo). **Hộp thoại trả hàng cũ đang gửi số dương.**
4. **Giới hạn xóa nợ của POS Profile chặn thu hồi KM mà không báo.** Ví dụ cửa hàng
   HAN_PAZZION đặt `write_off_limit = 1đ`. `submit_invoice` nuốt lỗi, nên KM không bao giờ được thu
   hồi. Thu hồi KM khi đổi trả nay không chịu giới hạn này (giới hạn dành cho thu ngân xóa tiền lẻ).
5. **`allow_return` đang tắt ở 46/46 Cài đặt POS** trên site dev, nhưng đã có 132 phiếu trả, vì cờ
   chưa từng có tác dụng. Patch `v1_15_0.bat_cho_phep_tra_hang` bật lại cho các cài đặt đang có
   trước khi server bắt đầu chặn.
6. **Tính trước phải chạy đủ `validate`.** Chỉ chạy `calculate_taxes_and_totals` thì thuế gồm
   trong giá cộng chiết khấu tổng đơn ra sai (3.135.020 thay vì 2.879.100).
7. **G2 bảng kê HĐĐT:** phiếu trả chỉ được vào bảng kê khi đơn gốc nằm cùng bảng kê đó. Khi đó các
   dòng âm trừ thẳng vào dòng bán cùng ngày.
8. **Combo:** combo là Product Bundle (mã không quản kho), nên được loại khỏi chặn "hàng dịch vụ".
   Phần trả **lẻ** từng món trong combo (C8) **chưa làm**, xem 6.8.
9. **KM tổng đơn kiểu phần trăm:** khi giỏ gộp đủ ngưỡng, giữ nguyên **số tiền** KM của đơn gốc,
   không tính lại % trên giỏ mới. KM không quy ra tiền: phần chuyển sang không vượt giá trị hàng mới.

Đã chạy thử 13 kịch bản trên HĐ thử (hoàn tác sau khi chạy), khớp mục 6.2. Khách trả ròng đúng
bằng giá phần giữ lại cộng hàng mới, trừ KM nếu còn hiệu lực, và HĐ gốc không treo công nợ ảo.

### 6.8 Phần server còn lại của đợt 1 (cập nhật 2026-10-06)

- **E2: đã làm.**
  - Áp dụng cho cửa hàng bật "điểm chuyển thành tiền ví" (`loyalty_to_wallet`, 34/46 cửa hàng trên
    site dev).
  - Trước đây trả hàng thì ERPNext giảm điểm nhưng **tiền ví đã cộng không bị thu lại**.
  - Nay thu lại phần tiền ví của hàng trả. Ví không đủ thì phần thiếu trừ vào tiền hoàn, ghi
    bút toán Nợ 131 (HĐ gốc) / Có TK chi phí của chương trình điểm.
  - Số điểm sau trả được dự tính theo đúng cách hệ thống chọn hạng, rồi đối chiếu sau khi lưu.
  - Chưa xử lý cửa hàng chỉ tích điểm mà không chuyển vào ví: hệ thống chưa từng dùng
    `redeem_loyalty_points` (0 hóa đơn).
- **D9: đã làm.** Hoàn tiền mặt vượt tiền mặt đang có trong ca thì chặn. Số tiền mặt trong ca tính
  y như lúc đóng ca. `calculate_exchange` trả kèm `cash_in_shift` để màn hình gợi ý.
- **C8 trả lẻ trong combo: dời sang đợt 2** (anh Quân đồng ý 06/10). Combo vẫn trả được nguyên combo.
- **Lỗi 3 và 4** (thuế mỗi đơn vị, tổng danh sách HĐ) nằm ở phần hiển thị của hộp thoại cũ. Màn
  hình mới lấy số từ `calculate_exchange`, nên sẽ xử lý cùng phần giao diện.

### 6.9 Bấm thử giao diện trên Chrome (2026-10-06, bench 8009, tài khoản Administrator)

Đã chạy 3 luồng, có chứng từ thật trên site dev, ghi chú "THỬ PM-FEAT-00060":

| Luồng | Chứng từ |
|---|---|
| Chỉ trả hàng | HĐ gốc AC2610060001, phiếu trả AC2610060004 |
| Đổi cùng giá | HĐ gốc AC2610060002, phiếu trả AC2610060005, HĐ mới AC2610060006 |
| Đổi nối tiếp sang hàng đắt hơn (vào từ Lịch sử hóa đơn) | HĐ gốc AC2610060006, phiếu trả AC2610060007, HĐ mới AC2610060008 |

AC2610060003 tạo ra nhưng chưa dùng.

Lỗi tìm ra khi bấm thử, đã sửa:

1. **Khách được ghi có ảo sau khi đổi hàng.** Trường "còn nợ" của phiếu trả giữ −2.879.100 dù sổ
   công nợ đã về 0, mà `credit_sales` đọc trường này làm số dư khách. Nay đặt lại trường này sau khi
   lưu (`_dat_lai_con_no_phieu_tra`). Dữ liệu thử AC2610060005 đã sửa tay về 0.
2. **Giỏ hiện sai số khi đang đổi hàng:** KM 10% của giỏ và Grand Total 4.500.000, trong khi số thu
   thật là 1.801.000. Nay giỏ ẩn dòng KM / coupon và hiện số server tính.
3. **Xóa giỏ không xóa KM tổng đơn**, nên giỏ trống hiện Grand Total −500.000. Lỗi này có sẵn ở
   `useInvoice.clearCart` / `resetInvoice`, dính cả bán thường. Đã thêm dòng xóa
   `transactionPreviewTotals`. Chưa kiểm lại được trên trình duyệt.
4. Dòng "Hàng mới" trong bảng tính lại đơn nay hiện giá **trước** phần KM chuyển sang.
5. **Số dư khách tính hai lần** khi ghi vào số dư (lỗi có sẵn ở `credit_sales`, PM-TASK-00267, sửa
   14/10). Số dư và nguồn tiền nay đọc theo sổ công nợ: khoản ghi có chỉ hiện ở HĐ gốc, phiếu trả
   luôn để "còn nợ" 0. Trên site dev, 15/36 khách có công nợ đổi số hiển thị: 9 khách giảm đúng
   một nửa (hết đếm đôi); 1 khách (AG260819160240) hết khoản ghi có ảo 229.900 vì sổ đã về 0;
   5 khách (NOIBO21, NOIBO51…, NOIBO53…, NOIBO60…, 1101818) trước hiện ghi có vài nghìn, nay hiện
   đúng theo sổ là còn nợ 90–190 nghìn (HĐ gốc thu thiếu, có từ trước, chưa rõ nguyên nhân).

Chưa sửa:

- **Lưu xong tự in HĐ mới**, mở hộp thoại in của trình duyệt (giống bán thường).
- **Lần gõ đầu vào ô tìm hàng sau khi tải trang hoặc đóng hộp thoại bị mất.** Có cả khi bán
  thường, chỉ thấy khi gõ bằng công cụ tự động, chưa rõ có ảnh hưởng thu ngân thật không.
