# CourtMate 2.3.1 — Tối ưu cloud và kiểm thử hồi quy

## Thay đổi đã triển khai

1. **Không xác nhận giữ chỗ quá hạn**: trước đây API quản trị có thể xác nhận một hold PENDING đã hết 20 phút nếu chưa có thao tác nào kích hoạt giải phóng. Bây giờ API kiểm tra và cập nhật hold hết hạn trong cùng transaction, trả HTTP 409 khi xác nhận muộn và ghi trạng thái CANCELLED.
2. **Rate limiter có bộ nhớ giới hạn**: dùng OrderedDict để giữ tối đa 4.096 IP gần nhất trong mỗi tiến trình, loại IP không hoạt động hơn 60 giây, 30 yêu cầu/phút/IP, trả Retry-After: 60 khi HTTP 429.
3. **Tính nhất quán của lịch trống**: API availability chỉ nhận ngày trong 0–365 ngày tới theo giờ Việt Nam, giống API tạo đặt sân.
4. **Chỉ mục SQLite**: thêm idx_bookings_day(date,start,id) và idx_bookings_expirable(hold_until) cho hold PENDING chưa PAID. Đây là tối ưu cấu trúc; không khẳng định tốc độ tăng bao nhiêu khi chưa benchmark tập dữ liệu đủ lớn.
5. **Danh sách cloud quản trị**: hỗ trợ limit (1–200, mặc định 200) và offset (0–100.000). Không SELECT public_token từ SQLite, giữ tương thích dữ liệu mà ứng dụng Android cũ đọc.

## Kiểm tra

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
cd ..
python scripts/smoke_http.py
```

Kỳ vọng: **21 bài pytest** và bài HTTP smoke test thành công. Năm test mới bao gồm lịch hết hạn, thời gian availability, rate limiter, index và phân trang.

Thử API phân trang (với server cục bộ đã bật):

```bash
curl -H 'Authorization: Bearer YOUR_DEV_TOKEN' \
  'http://127.0.0.1:8000/v1/admin/bookings?limit=50&offset=0'
```

## Phạm vi và giới hạn

- Chưa chỉnh luồng đặt sân/offline trên Android; hai cơ sở dữ liệu chưa đồng bộ.
- Rate limiter chỉ hoạt động độc lập trong từng process, không thay thế Redis/WAF.
- SQLite index được tạo khi app khởi động; cần backup trước khi nâng cấp dữ liệu lớn.
- CI backend/Android xanh không thay cho kiểm thử giao diện trên thiết bị vật lý.
- Không có ngân hàng/PSP thật; không nên triển khai với dữ liệu khách hoặc thanh toán thật.
