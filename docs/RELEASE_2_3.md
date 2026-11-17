# CourtMate 2.3 — Stabilization / Portfolio Preview

Phạm vi: sửa khả năng build, kiểm thử HTTP thật và đóng gói demo portfolio. **Không** thay đổi logic dữ liệu Android SQLite, hợp đồng API thanh toán hay đồng bộ offline/cloud.

## Thực hiện trên nhánh `upgrade/v2.3`

- Chuyển GitHub Action Android SDK `setup-android@v3` (đòi package `tools` đã bị Google xóa) thành `@v4`.
- Chọn gói Android SDK phát hành `platforms;android-37.0`; Build Tools 36.0.0; giữ AGP/Gradle và Java 25 theo dự án gốc.
- Bổ sung kiểm tra file APK và lưu artifact 14 ngày, để không nhầm CI pass với APK chưa tạo.
- Giữ 16 bài FastAPI cũ; thêm script thực hiện chuỗi HTTP thật ở 127.0.0.1 với SQLite tạm; không sử dụng dữ liệu người dùng.
- Sửa ngày mặc định trên website theo `Asia/Ho_Chi_Minh` để không lệch khi trình duyệt ở múi giờ khác.
- Bổ sung ảnh giao diện, README dạng portfolio, tài liệu deploy Render static và checklist QA.

## Những giới hạn vẫn còn

- Không đồng bộ lịch Android và cloud; chưa chuyển sang Room/MVVM hoàn toàn.
- Cloud dùng shared Admin token, không có RBAC từng nhân viên.
- Chưa kết nối thanh toán ngân hàng thật, chưa có refund/reconciliation.
- Demo static chỉ là mô phỏng; API FastAPI cục bộ có thể chạy thật nhưng không đủ production hardening.
- Build APK phải xác minh qua GitHub Actions và vẫn phải cài chạy trên thiết bị để kiểm tra giao diện.

## Kiểm chứng

GitHub Actions: <https://github.com/nguyenhonggiang2407/CourtMate/actions>.
Chạy locally: `cd backend && python -m pytest tests -q` và `python scripts/smoke_http.py` từ gốc dự án.
