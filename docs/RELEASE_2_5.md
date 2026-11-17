# CourtMate 2.5 — Cloud sync foundation (chưa phải đồng bộ SQLite hai chiều)

## Mục tiêu và thay đổi có thể kiểm chứng

Bản nâng cấp này giữ nguyên các luồng nghiệp vụ 2.4, thêm ba cải tiến thực tế:

1. **Change feed theo `seq` tăng dần**: `GET /v1/admin/changes?after=0&limit=100` (cần phiên Admin hoặc Staff). Máy chủ ghi thay đổi sân và lịch bằng SQLite trigger trong cùng transaction, bao gồm cả lịch tự hết hạn. Mỗi sự kiện có `seq`, `resource`, `resource_id`, `action`, `created_at`, `record` (trạng thái *hiện tại*). Khi xóa, `record=null` và `action=DELETE`. `next_cursor` và `has_more` giúp client đọc nhiều trang, không dựa vào đồng hồ máy khách.
2. **Chống gửi trùng khi mạng yếu**: `POST /v1/admin/bookings` nhận thêm `client_request_id` tùy chọn (16–80 ký tự chữ/số/_/-). Cùng mã và cùng trường lịch sẽ trả về **cùng booking id**; đổi dữ liệu nhưng dùng lại mã sẽ nhận HTTP 409. Gửi công khai không được cấp mã này. Android tạo UUID cho mỗi thao tác lưu lịch; server xử lý retry an toàn khi giữ nguyên UUID.
3. **Trải nghiệm Cloud Android**: chọn sân từ danh sách đang hoạt động, hộp chọn ngày/giờ, danh sách lịch phân trang **100 lịch/trang** với hai nút trước/sau; không cần nhập số ID sân thủ công.

## Cách sử dụng change feed

```http
GET /v1/admin/changes?after=0&limit=100
Authorization: Bearer <STAFF_SESSION_TOKEN>
```

Ví dụ phản hồi (thông tin minh họa):

```json
{
  "events": [
    {"seq": 1, "resource": "court", "resource_id": 1, "action": "UPSERT", "created_at": "2026-11-17T00:00:00.000Z", "record": {"id": 1, "name": "Sân A", "price_hour": 100000, "active": 1}}
  ],
  "next_cursor": 1,
  "has_more": false,
  "server_time": "2026-11-17T00:00:01+00:00"
}
```

**Quy tắc xử lý**: đọc theo `seq` tăng dần; `UPSERT` ghi đè bản ghi theo `(resource,resource_id)`; `DELETE` xóa bản ghi cache; chỉ lưu `next_cursor` sau khi **toàn bộ trang** đã được áp dụng thành công. Sự kiện có `record` tại thời điểm đọc, không phải bản chụp lịch sử vào thời điểm sự kiện xảy ra. Không nên dùng bảng này làm sổ audit tài chính. Endpoint chỉ trả về dữ liệu cho Staff/Admin đã xác thực; **không bao giờ trả `public_token`**.

**Điều không làm**: không tự động ghi dữ liệu này vào SQLite vận hành offline của Android, không gửi invoice/phiên chơi từ offline lên cloud, không có conflict resolver cho hai nguồn lịch. Để tránh double booking, hiện vẫn phải dùng **một nguồn đặt lịch duy nhất cho từng sân**, không mở đồng thời hai quy trình đặt lịch độc lập.

## Nâng cấp SQLite server hiện có

- **Sao lưu file DB trước** khi triển khai và kiểm tra khả năng phục hồi.
- Khi khởi động, `init_db()` tạo `cloud_changes`, trigger và thêm cột `bookings.client_request_id` + unique index nếu thiếu. Không xóa hay ghi đè booking/court cũ.
- Nếu chưa có sự kiện nào nhưng đã có dữ liệu cũ, tự tạo snapshot sự kiện ban đầu cho tất cả sân và lịch. Chạy `init_db()` lại không tạo thêm sự kiện giống nhau.
- Không sửa `app/src/main/java/.../data/DatabaseHelper.java` trong đợt này; database Android vẫn là dữ liệu offline độc lập.
- Change log được giữ lại toàn bộ (chưa có lịch trình retention/snapshot compaction). Khi dữ liệu lớn, cần lên kế hoạch chuyển sang PostgreSQL hoặc thiết kế snapshot + retention có cursor-resync.

## Kịch bản QA có thể chạy

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python ../scripts/smoke_http.py
```

Các kiểm thử mới kiểm tra: quyền đọc feed và việc không lộ mã bí mật; cursor phân trang; tài khoản Staff bị khóa; sự kiện khi lịch giữ chỗ hết hạn; tự sinh snapshot cho DB cũ; idempotency và dữ liệu xung đột; nhiều yêu cầu lặp đồng thời; tombstone khi xóa.

**Android**: CI chạy `testDebugUnitTest assembleDebug`. Cần cài APK trên máy/emulator và thử: đăng nhập Staff, chọn sân từ dropdown, chọn ngày/giờ, tạo lịch, xem trang kế, hủy lịch, đăng xuất rồi chắc chắn không còn thấy dữ liệu khách. Không coi CI xanh là bằng chứng các thao tác UI này đã được kiểm chứng trên máy thật.

## Bảo mật và triển khai

- Trong 2.5, `COURTMATE_ALLOW_LEGACY_ADMIN=true` vẫn là mặc định **chỉ để tương thích nâng cấp từ 2.4**. Khi đã tạo Admin theo tài khoản, đặt `COURTMATE_ALLOW_LEGACY_ADMIN=false`, đổi token cũ và khởi động lại backend. Không dùng legacy key cho môi trường kinh doanh.
- Chỉ dùng HTTPS công khai; mật khẩu và mã truy cập không được đưa vào URL. Không commit `.env` hay dữ liệu thật.
- Chưa có Render backend public/DB bền vững được xác minh. `render.yaml` hiện có chỉ làm demo HTML tĩnh, không có giao dịch thật.
- Chưa có real bank integration, hoàn tiền thực, xử lý sự kiện PSP theo hợp đồng, khóa phân tán hay chống gian lận đủ cho production.

## Bước tiếp theo hướng 2.6

1. Chuyển hoạt động tạo/đổi/hủy lịch offline vào API thống nhất, có local outbox và mapping ID trước khi nhận dùng đồng thời.
2. Áp dụng change feed vào repository cache riêng và lưu cursor theo transaction; giao diện Android hiển thị trạng thái đồng bộ và cách xử lý conflict.
3. Kiểm thử mất mạng và multi-device trên emulator, kiểm tra tính nhất quán sau reconnect; tích hợp cảnh báo người dùng nếu lịch từ cloud/SQLite đang bị trùng.
4. Thực hiện backup mã hóa, audit log theo tài khoản và lựa chọn lưu trữ bền vững.
