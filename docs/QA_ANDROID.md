# Android QA checklist — CourtMate 2.3

## CI (không cần điện thoại)

- [ ] Android SDK setup thành công: API 37.0, Build Tools 36.0.0.
- [ ] `testDebugUnitTest` thành công.
- [ ] `assembleDebug` sinh `app/build/outputs/apk/debug/app-debug.apk` khác 0 byte.
- [ ] APK `courtmate-debug-apk` có thể tải ở GitHub Actions artifacts.
- [ ] FastAPI pytest và HTTP smoke test đều pass.

## Thiết bị / emulator (bắt buộc để xác nhận chức năng UI)

- [ ] APK cài được (`adb install -r ...`) trên một Android API 24+.
- [ ] Mở ứng dụng không crash; tạo Admin lần đầu (không có mật khẩu demo hardcode).
- [ ] Tạo sân, khách, lịch, kiểm tra chống trùng; thử slot đầu/cuối giờ.
- [ ] Bắt đầu/kết thúc phiên, thêm dịch vụ, cọc, thanh toán; không thu tiền hai lần.
- [ ] Xem dashboard và hóa đơn; đăng xuất, kiểm tra quyền Staff/Admin.
- [ ] Cloud booking qua HTTPS staging, token không lộ, chỉnh trạng thái sân/lịch.
- [ ] Offline và online không được coi là đồng bộ hai chiều; tuyệt đối không vận hành đồng thời chung sân.
- [ ] Sao lưu/khôi phục bằng dữ liệu giả; không dùng PII thật hoặc tài khoản thật.
- [ ] Dùng thử trên màn hình nhỏ/lớn, đổi xoay màn hình, tăng cỡ chữ, mạng kém.

**Trạng thái:** checkboxes chỉ được đánh dấu sau khi có log/ảnh/bằng chứng. CI JVM test và assemble không thay thế kiểm thử giao diện emulator/thiết bị.
