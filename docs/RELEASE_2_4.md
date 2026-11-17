# CourtMate 2.4.0-demo — Cloud staff authentication / lịch cloud theo ngày

## Thay đổi đã triển khai

- Tạo tài khoản quản trị một lần, không dùng tài khoản/mật khẩu mẫu cố định.
- Quản lý tài khoản có vai trò `ADMIN`, `STAFF`, tắt tài khoản và thu hồi phiên tức thì.
- Đăng nhập cloud bằng mật khẩu băm PBKDF2-HMAC-SHA256 và phiên 12 giờ; đăng xuất thu hồi token.
- Kiểm soát quyền **trên backend**: Staff có thể xem, tạo và xử lý lịch; không thể thêm/sửa sân, quản lý nhân viên hoặc tạo yêu cầu thanh toán.
- Android: đăng nhập bằng username/password qua HTTPS, đóng phiên cloud, lọc lịch/summary theo ngày; bật quyền mở Cloud cho Staff cục bộ, nhưng vai trò cloud được kiểm tra độc lập trên server.
- Giữ tương thích token quản trị legacy theo `COURTMATE_ALLOW_LEGACY_ADMIN=true`, khuyến cáo **tắt khi đã chuyển sang tài khoản riêng**.
- Không thay đổi dữ liệu cũ khi `init_db()` chạy trên database SQLite đang có.

## Các bước nghiệm thu

1. `cd backend && python -m pytest tests -q` — kỳ vọng 30 bài API đạt.
2. `python scripts/smoke_http.py` tại repo root — chạy smoke HTTP thực tế bằng uvicorn cục bộ.
3. CI GitHub `testDebugUnitTest assembleDebug` thành công, tải artifact APK và cài trên thiết bị Android thật.
4. Tạo Admin đầu tiên, đăng nhập; tạo Staff; Staff không sửa được sân (`403`), vẫn xem và tạo lịch được.
5. Đăng xuất, thử token cũ (`401`); vô hiệu hóa Staff, xác nhận phiên trước mất hiệu lực.
6. Cho 2 thiết bị kết nối cùng cloud: tạo lịch bên A, bấm Làm mới ngày đó bên B, thấy cùng dữ liệu; không được coi là sync SQLite offline.

## Giới hạn còn lại — chưa phải production

- **Chưa đồng bộ 2 chiều SQLite offline và cloud**. Không dùng hai nguồn lịch cho cùng sân trong kinh doanh thực.
- Đăng nhập có rate limiter trong RAM từng process, không phải chống brute-force quy mô lớn.
- Admin key legacy vẫn được hỗ trợ để chuyển tiếp; phải tắt thủ công.
- Chưa có kiểm thử instrumentation trên điện thoại do CI mới thực hiện JVM tests + APK build.
- Cloud SQLite chưa hỗ trợ HA nhiều máy chủ; đặt DB trên volume bền vững và sao lưu trước triển khai.
- Chưa có thanh toán ngân hàng thật hoặc hỗ trợ hoàn tiền tự động.
