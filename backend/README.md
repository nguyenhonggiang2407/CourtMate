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

## Cloud staff accounts (CourtMate 2.4 demo)

**Transition from the old shared key:** legacy admin Bearer remains available while
`COURTMATE_ALLOW_LEGACY_ADMIN=true` (default for compatibility). **Disable it after provisioning named accounts.**
Keep `COURTMATE_ADMIN_TOKEN` secret and rotate any previously shared value.
Use HTTPS for all remote requests; login is not suitable for plaintext HTTP.

Bootstrap the first Admin **once** with the legacy key:

```bash
curl -X POST https://your-courtmate-host/v1/auth/bootstrap \
  -H 'Authorization: Bearer YOUR_EXISTING_ADMIN_TOKEN' \
  -H 'Content-Type: application/json' \
  --data '{"username":"owner01","password":"USE_YOUR_OWN_12_PLUS_CHAR_PASSWORD"}'
```

Avoid entering real passwords on shared terminals or in shell history. When you
have server-shell access, prefer `python manage_staff.py create-admin` (uses
`getpass`, does not echo the password). Remove sensitive commands from shell
history and use a secrets manager.

Authenticate with `POST /v1/auth/login` and send the returned `access_token`
with `Authorization: Bearer ...`. Responses include the account role and
`expires_at` (12 hours). `POST /v1/auth/logout` revokes the current token;
`GET /v1/auth/me` returns the current role. Sessions store SHA-256 token hashes,
not raw bearer tokens. Passwords use PBKDF2-HMAC-SHA256 with distinct salts.

Admin-only routes:
- `POST /v1/admin/courts`, `PATCH /v1/admin/courts/{id}` and Android POST alias
- `GET /v1/admin/staff`, `POST /v1/admin/staff`, `PATCH /v1/admin/staff/{id}` (active true/false)
- `POST /v1/admin/bookings/{id}/bank-intent`

Staff-or-Admin routes: list courts, view summary and bookings, create a cloud booking,
confirm/cancel eligible bookings. This is **server-enforced RBAC**, not only
button visibility. Disabling an account immediately deletes its live sessions.
The last active Admin cannot be disabled.

Use this workflow after the first Admin is created:

1. Log in as the new Admin and create individual Staff accounts with `/v1/admin/staff`.
2. Switch Android Cloud UI from legacy token input to username + password.
3. Set `COURTMATE_ALLOW_LEGACY_ADMIN=false` and restart the server.
4. Verify the shared key returns HTTP 401 and named Admin/Staff sessions work.

Login rate limiting is **per-process best effort**: 10 requests / 5 min / IP+username,
max 4,096 buckets. Production use requires Redis/WAF/shared throttling, audit logs,
credential rotation, monitoring and backup validation. No default account or
password is embedded in the project.

**Current cloud scope:** Android Cloud screen shows one date's remote bookings
(up to 200 results) across devices. It does **not** push local SQLite reservations
to the server, merge conflicts, or synchronize local invoices/payments. Avoid
using offline and cloud schedules in parallel for the same physical court.

## CourtMate 2.5 — Change feed & an toàn khi gửi lại

- `GET /v1/admin/changes?after=0&limit=100` dành cho Admin/Staff. Trả `events`, `next_cursor`, `has_more`, `server_time`, theo thứ tự `seq` tăng dần. Mỗi event có `resource` (`court`/`booking`), `resource_id`, `action`, `record`. Sự kiện `DELETE` có `record=null`. `public_token` không xuất hiện trong feed.
- Cursor là số tăng dần do SQLite server tạo, không dựa vào giờ thiết bị. Chỉ lưu cursor sau khi client đã áp dụng thành công toàn bộ trang. Dữ liệu trong `record` là trạng thái hiện tại, không phải ảnh chụp lịch sử.
- API tạo lịch nội bộ (`POST /v1/admin/bookings`) nhận `client_request_id` tùy chọn (16–80 ký tự chữ/số/gạch nối/gạch dưới). Gửi lại cùng mã và cùng thông tin trả về cùng booking; cùng mã nhưng payload thay đổi trả `409`. Public booking không chấp nhận trường này. Mã giúp client retry với **cùng id**, không thay thế queue offline.
- `init_db()` tự bổ sung cột & index idempotency, tạo trigger change feed; nếu DB cũ có lịch nhưng chưa có event, lần đầu sẽ tạo snapshot. Nên sao lưu và chạy thử migration trước khi nâng cấp server đang dùng.
- Android Cloud có trang 100 lịch, dropdown sân hoạt động, chọn ngày giờ; **SQLite Android offline vẫn chưa đồng bộ hai chiều**. Chỉ sử dụng một nguồn lịch cho mỗi sân khi vận hành demo.

Xem [ghi chú kỹ thuật 2.5](../docs/RELEASE_2_5.md) và quy trình QA. Token quản trị dùng chung còn bật mặc định chỉ để tương thích; hãy tắt `COURTMATE_ALLOW_LEGACY_ADMIN` sau khi tạo tài khoản Admin/Staff.
