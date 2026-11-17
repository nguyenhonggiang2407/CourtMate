# Deploy demo CourtMate 2.3

## Chọn đúng bản demo

1. **Static portfolio demo (khuyến nghị, an toàn)**: `demo/index.html` là bản tương tác độc lập, không kết nối backend, không xử lý tiền hay dữ liệu cá nhân. Có thể mở trực tiếp trên máy hoặc host miễn phí trên Render Static Site. Giao diện này **mô phỏng** nghiệp vụ để trình diễn.
2. **FastAPI backend thật (chỉ dùng thử)**: `backend/static/index.html` kết nối API, SQLite server riêng. Android SQLite **không đồng bộ** sang cloud. Không nên công khai nhận đặt thật khi thiếu chống spam, xác thực tài khoản, database bền vững và xử lý xung đột.

## A. Render Static Site (Blueprint)

1. Mở <https://dashboard.render.com/blueprints>, chọn **New Blueprint Instance**; kết nối repo `nguyenhonggiang2407/CourtMate` nếu chưa kết nối.
2. Chọn workspace bạn muốn sử dụng, nhánh `upgrade/v2.3`, file `render.yaml`.
3. Xem lại cấu hình `courtMate-v23-preview` (tên tài nguyên phụ thuộc vào khả năng trùng tên), gói `free`. Chỉ tạo **static site** mới; không đụng đến các service khác.
4. Sau khi Render báo `Live`, dùng URL được **Render hiển thị**; không tự đoán URL. Truy cập trang và kiểm thử chọn sân, ngày, tạo/hủy yêu cầu mô phỏng.
5. Khi PR lên `main`, sửa trường `branch` trong `render.yaml` sang `main` nếu muốn auto deploy bản ổn định.

Giới hạn: bản static này không có xác thực nhân viên, không lưu dữ liệu lên server, không gửi webhook và không tạo giao dịch ngân hàng.

## B. Chạy FastAPI API thật ở localhost

Từ thư mục gốc dự án:

```bash
python -m pip install -r backend/requirements-dev.txt
# macOS/Linux:
export COURTMATE_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export COURTMATE_PUBLIC_BOOKING=true
cd backend && python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Trên PowerShell: đặt `$env:COURTMATE_ADMIN_TOKEN` bằng token ngẫu nhiên và `$env:COURTMATE_PUBLIC_BOOKING = "true"` trước khi chạy. Mở `http://127.0.0.1:8000/`, `http://127.0.0.1:8000/docs`. Phải tạo sân trước qua API `/v1/admin/courts` với header Bearer token; không có tài khoản mặc định.

Test HTTP thực sự, không cần emulator:

```bash
python scripts/smoke_http.py
```

Script tự tạo SQLite tạm, khởi động Uvicorn ở `127.0.0.1`, tạo sân và đặt lịch giả, kiểm tra HTTP, trùng lịch, tra cứu và hủy rồi xóa DB tạm. **Không chạy với dữ liệu thật.**

## C. Nếu deploy API FastAPI online

Trước khi public cần HTTPS, per-staff auth/RBAC, CAPTCHA/rate limit ở hạ tầng, PII retention, backup dữ liệu, database bền vững và luồng thanh toán đã được đối tác kiểm chứng. Dùng môi trường sandbox và thông tin giả khi thử.

Nếu dùng Render Free Python Web Service: rootDir `backend`, build `pip install -r requirements.txt`, start `uvicorn app:app --host 0.0.0.0 --port $PORT`, health `/health`, tạo bí mật `COURTMATE_ADMIN_TOKEN` riêng cho service, `COURTMATE_PUBLIC_BOOKING=false` mặc định. **SQLite trên hệ thống file của Render Free không bền vững, sẽ mất khi ngủ/restart/redeploy**; không nên nhận lịch thật trên cấu hình này. Tham khảo <https://render.com/docs/free>.

## Phần chưa được thực hiện

Chưa tạo service Render hay xác nhận một URL public. Việc triển khai cần bạn lựa chọn workspace Render và quyền kết nối repo. Tránh tạo thay/ghi đè service của các dự án khác.
