# Test POS trên điện thoại bằng ngrok

Để test giao diện POS Next trên điện thoại (cùng mạng WiFi với máy dev), dùng ngrok để mở tunnel tới Vite dev server.

## Chuẩn bị

1. **Cài ngrok** (nếu chưa có):
   - Tải: https://ngrok.com/download
   - Hoặc: `npm install -g ngrok` / `snap install ngrok`

2. **Chạy backend Frappe** trên port **8010** (như bình thường):
   ```bash
   # Từ thư mục bench (ví dụ sites của bạn)
   bench start
   ```

3. **Chạy Vite dev** (từ thư mục POS):
   ```bash
   cd apps/pos_next/POS
   npm run dev
   ```
   Server chạy tại http://localhost:8080.

## Chạy ngrok

Mở terminal mới (giữ `npm run dev` và backend đang chạy):

```bash
cd apps/pos_next/POS
npm run dev:ngrok
```

Hoặc trực tiếp:

```bash
ngrok http 8080
```

ngrok sẽ in ra URL dạng `https://xxxx-xx-xx-xx-xx.ngrok-free.app`. Mở URL này trên điện thoại (cùng WiFi) để vào POS.

## Lưu ý

- **Backend** phải chạy trên **8010**. Vite proxy sẽ gửi `/api`, `/app`, `/files`... từ ngrok về `127.0.0.1:8010`.
- Lần đầu mở URL ngrok trên trình duyệt có thể có trang cảnh báo của ngrok (free tier); bấm tiếp tục vào site.
- Camera (chụp ảnh chấm công) chỉ hoạt động trên **HTTPS** hoặc **localhost**; dùng URL ngrok (https) thì camera trên điện thoại sẽ hoạt động bình thường.
