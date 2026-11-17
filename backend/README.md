# CourtMate Cloud – pilot API (0.3.1 / CourtMate 2.3.1-demo)

FastAPI backend for a **centralized ONLINE booking schedule** shared by multiple Android clients and customers. This is a **separate cloud schedule**, not a replica of the local Android SQLite DB. Do **not** regard local bookings and cloud bookings as mutually exclusive while deploying it: migrate or use one canonical booking source before going live.

## Quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # on Windows use .venv\\Scripts\\activate
pip install -r requirements.txt
export COURTMATE_ADMIN_TOKEN=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
export COURTMATE_PUBLIC_BOOKING=true  # enable ONLY once the venue is ready
uvicorn app:app --host 127.0.0.1 --port 8000
```

In production terminate HTTPS with a vetted reverse proxy, restrict allowed origins, add WAF/rate-limiting, monitoring, password-based staff accounts and a real transactional DB such as PostgreSQL if running more than one app process. `COURTMATE_DB` should be on a durable private volume. Do not expose HTTP plaintext on a public network.

Create a court (use the same `COURTMATE_ADMIN_TOKEN` as on the server):

```bash
curl -X POST http://127.0.0.1:8000/v1/admin/courts \\
  -H 'Authorization: Bearer YOUR_TOKEN' -H 'Content-Type: application/json' \\
  -d '{"name":"Sân A","price_hour":120000}'
```

Then open `/` to submit a public reservation; `/v1/admin/bookings` gives all client devices the same live server records. `PENDING` reserves the slot 20 minutes; staff must PATCH the booking to `CONFIRMED` before the hold expires. The public web UI **does not take money**.

## Bank payment integration – webhook adapter only

`POST /v1/admin/bookings/{id}/bank-intent` requires a trusted PSP `COURTMATE_PAYMENT_URL_TEMPLATE` containing `{reference}` and `{amount}`. Templates are explicitly NOT a substitute for a real PSP API. Integrate the PSP's actual create-payment endpoint and signed server webhook into the backend. We intentionally do not ship a fictional bank integration.

For a correctly signed PSP adapter POST `/v1/provider/webhooks/payment` with `X-Courtmate-Timestamp` as Unix epoch and `X-Courtmate-Signature` = HMAC-SHA256 over `{timestamp}.` + **raw JSON body** using the server-only `COURTMATE_GATEWAY_WEBHOOK_SECRET`. Body shape is `{"event_id":"...","reference":"CM...","amount":120000,"currency":"VND","status":"SUCCESS"}`. The backend ensures idempotent event processing and matching amount/reference; the frontend cannot set `PAID`. Build your provider-specific adapter to normalize *provider-verified* events; do not send browser data directly to this endpoint.

## Các API bổ sung trong 2.2.0-demo

- `PATCH /v1/admin/courts/{id}`: cập nhật tên, giá theo giờ, hoặc `active` (0/1). Android `HttpURLConnection` dùng alias `POST /v1/admin/courts/{id}/update` cùng payload.
- `GET /v1/admin/summary?date=YYYY-MM-DD`: tổng số lịch, PENDING/CONFIRMED/CANCELLED, số sân hoạt động và chỉ số tiền thực thu từ `payment_status=PAID`. `amount_to_collect` là lịch CONFIRMED chưa PAID; số liệu áp dụng **chỉ cho cloud**, không tính lịch Android SQLite.
- `POST /v1/public/bookings/cancel`: payload `{"id":123,"access_token":"..."}`, chỉ được hủy lịch `PENDING` và `UNPAID`. Hủy nhiều lần cùng một đơn được chấp nhận; lịch CONFIRMED phải do quản trị xử lý.
- Website cung cấp ô nhập mã đơn và token bí mật để tra cứu/hủy; token không lưu vào localStorage và cần tự lưu nếu muốn kiểm tra sau khi tải lại trang.
- API không trả `public_token` cho Admin; chỉ gửi `access_token` cho khách tại thời điểm tạo lịch.
- Yêu cầu đặt cùng ngày phải có giờ bắt đầu nằm trong tương lai, xét theo `Asia/Ho_Chi_Minh`.

**Chạy tests:** `python -m pip install -r requirements-dev.txt` rồi `python -m pytest tests -q` từ thư mục `backend`.

## Tối ưu và API tương thích 2.3.1

- `GET /v1/admin/bookings` hỗ trợ `limit=1..200`, `offset=0..100000`. Mặc định vẫn trả tối đa 200 lịch để tương thích Android đang dùng. Chỉ chọn cột cần thiết, không đọc `public_token`.
- `GET /v1/public/availability`: ngày phải trong 0–365 ngày tới theo múi giờ Việt Nam.
- Admin không thể xác nhận một yêu cầu giữ chỗ đã hết hạn: backend cập nhật `CANCELLED` và trả `409`.
- Bộ giới hạn yêu cầu công khai 30 yêu cầu/phút/IP dùng tối đa 4.096 IP gần đây trong mỗi process, trả `Retry-After: 60` khi `429`. **Không thay thế WAF hoặc Redis** khi chạy nhiều process.
- `init_db()` tạo thêm chỉ mục truy vấn theo ngày và lịch PENDING hết hạn. Hãy sao lưu DB và tính thời gian khóa tạo index khi migrate một DB lớn.

Xem [báo cáo tối ưu 2.3.1](../docs/OPTIMIZATION_2_3_1.md).

## Explicit limitations

- Local Android SQLite and cloud data are **not synchronized**. No multi-branch conflict resolution, offline queue or automatic local booking mirroring.
- Admin uses one server API key shared with admin devices and held only in Android process memory. This is a starter integration, not production RBAC. In production add per-staff tokens, revocation and key rotation.
- Public endpoints have only a best-effort in-process limiter for booking, lookup and cancellation; there is no CAPTCHA, SMS verification, distributed rate limit, fraud control, deposits or cancellation notifications. Must be hardened before public use.
- No actual bank connection. To enable a real payment flow, obtain partner contract, implement actual provider verification and run an end-to-end sandbox test.
- App `SQLite` backup contains local user hashes; exported backup is not encrypted. Store backup files securely.

### Docker Compose, truy cập nội bộ

```bash
cd backend
export COURTMATE_ADMIN_TOKEN=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
docker compose up --build -d
```

Port bind `127.0.0.1:8000` only; use HTTPS proxy with real certificate and configure domain before Android can connect. Persist DB in named volume `courtmate_data`, back up this volume periodically. Before exposing the public portal, enforce CAPTCHA/verification, per-user staff auth, firewall and production-grade monitoring.
