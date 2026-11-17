## 2.5.0 — Change feed cloud, retry an toàn và cải tiến Android (nhánh feature/v2.5-sync-foundation)

- Thêm bảng SQLite `cloud_changes` cùng trigger ghi sự kiện trong transaction, API staff `GET /v1/admin/changes` có cursor `seq`, phân trang và tombstone.
- Tự backfill snapshot cho dữ liệu cloud cũ trong `init_db()`, không xóa lịch; cột mới `client_request_id` + unique index.
- Cho phép tạo lịch nội bộ với mã gửi lại: cùng mã + nội dung trả lại một booking, mã tái sử dụng với nội dung khác bị từ chối.
- Android: bộ chọn sân hoạt động, chọn ngày/giờ, xem 100 lịch/trang, gửi UUID cho lịch mới.
- Bổ sung 7 bài kiểm thử backend (30 lên 37), smoke HTTP kiểm tra change feed và idempotency.
- Chưa có đồng bộ SQLite offline hai chiều, audit log độc lập hay môi trường production. Chi tiết: [Release 2.5](docs/RELEASE_2_5.md).

## 2.4.0-demo — Cloud staff accounts và Android remote schedule

- Backend: tạo Admin một lần, tạo/vô hiệu hóa tài khoản STAFF/ADMIN, login/logout, token phiên 12 giờ, RBAC theo endpoint.
- Mật khẩu PBKDF2, salt riêng; token chỉ lưu dạng hash phía server; giới hạn đăng nhập theo IP+tài khoản trong mỗi process.
- Android: đăng nhập HTTPS bằng tài khoản, thoát phiên, ẩn thao tác quản trị với Staff, lọc lịch/summary cloud theo ngày.
- Có chế độ chuyển tiếp token quản trị legacy, cần chủ động tắt khi đã chuyển qua tài khoản nhân viên.
- Chưa merge lịch offline và cloud; không bảo đảm tính nhất quán nếu vận hành hai nguồn đồng thời.

## 2.3.1 — Tối ưu cloud (nhánh optimize/v2.3.1)

- Chặn Admin xác nhận giữ chỗ PENDING đã hết hạn, đồng thời trả slot cho yêu cầu mới.
- Giới hạn bộ nhớ rate limiter theo process, dọn IP không hoạt động và trả Retry-After khi HTTP 429.
- Thêm SQLite index cho truy vấn theo ngày và lịch giữ chỗ sắp hết hạn.
- API admin bookings hỗ trợ phân trang, tránh đọc public_token từ DB; availability kiểm tra khoảng ngày hợp lệ.
- Tăng từ 16 lên 21 bài kiểm thử FastAPI, giữ tương thích phần Android và HTTP smoke test.
- Chưa đồng bộ lịch SQLite Android/cloud và chưa có payment provider thực tế.

## 2.3.0 (nhánh upgrade/v2.3 — ổn định và demo)

- Sửa GitHub Actions Android SDK setup và tên gói Android API 37.0 để build APK debug.
- Bổ sung kiểm thử HTTP với Uvicorn thật, database tạm và dữ liệu giả.
- Căn ngày mặc định website theo múi giờ Việt Nam (Asia/Ho_Chi_Minh).
- README portfolio, ảnh demo, Render static blueprint, quy trình QA Android và hướng dẫn triển khai.
- Giữ nguyên logic đặt sân, thanh toán và dữ liệu hiện có, không thay đổi hai nguồn lịch Android/cloud.

## 2.2.0-demo — GitHub-ready cloud improvements (17/11/2026)

- Thêm API cập nhật sân cloud (đổi tên, giá/giờ, tạm đóng/mở). Tạm đóng chặn lịch mới, không tự hủy lịch cũ.
- Thêm dashboard thống kê cloud theo ngày (lịch chờ, xác nhận, hủy, thực thu khi gateway báo PAID, và số tiền cần thu).
- Khách có thể tra cứu trạng thái và hủy lịch PENDING/UNPAID bằng cặp mã đơn + token bí mật; website hiển thị mã để tự lưu.
- Chặn thời gian đặt sân trong quá khứ theo múi giờ Việt Nam, chuẩn hóa tên sân và kiểm tra query ngày.
- Hạn chế tốc độ tra cứu công khai; API dành cho nhân viên không xuất customer public_token.
- Màn hình Android Cloud bổ sung thống kê, danh sách sân và nút tạm đóng/mở trên cloud.
- 16 bài kiểm thử API backend đạt tại môi trường đóng gói; bổ sung GitHub Actions, hướng dẫn push, quy tắc giữ bí mật khi công khai repo.
- Giữ nguyên SQLite schema v7, applicationId và luồng demo 2.1.0; không hứa hẹn đồng bộ SQLite–cloud hoặc PSP thanh toán thật.
- Chưa build APK/instrumentation test vì môi trường hiện tại không có Android SDK và Gradle distribution.

## 2.1.0-demo — Giao diện mới và dữ liệu demo (10/11/2026)

- Giữ project Android Studio + backend từ 2.0.0-alpha; không thay đổi applicationId hoặc SQLite schema v7.
- Thiết kế lại Dashboard với hero xanh đậm, KPI, doanh thu, truy cập nhanh và thanh điều hướng dưới.
- Làm mới màn hình đăng nhập, header các trang lịch đặt, quản lý sân, khách hàng, vận hành, thống kê; thống nhất token màu và card.
- Dựa trên *ngôn ngữ thiết kế* của app.zip tham khảo (hero tối, card sáng, bo góc, navigation), không sao chép mã nghiệp vụ hay tài sản thương hiệu ứng dụng sạc xe.
- Tạo DemoDataSeeder: 3 khách demo, 3 HLV, 3 lớp và lịch lớp, 3 sự kiện, 3 ưu đãi, 3 lịch vãng lai, 3 lịch đặt tương lai, 3 phiên kết thúc đã trả tiền và 3 phiếu thuê đang mở; bổ sung thiết bị thuê thứ 3. Dữ liệu sản xuất hiện hữu không bị tự điền khi nâng cấp.
- Tự động nạp demo khi cài hoàn toàn mới; với dữ liệu hiện có, Admin chọn **Cài đặt > Nạp dữ liệu demo** (có xác nhận).
- Dữ liệu demo gắn nhãn [DEMO]; lần nạp thứ hai không nhân đôi các bản ghi còn tồn tại. Không tự tạo người dùng, token, cấu hình đèn.
- Kiểm thử độc lập SQLite v7: lần 1 thêm 52 bản ghi, lần 2 thêm 0, foreign_key_check không lỗi. XML 61/61 parse được; chưa build Android APK tại môi trường này.

# Changelog

## 2.3.0 (development branch)

- CI Android: setup-android v4, SDK API 37.0, verify/upload APK debug.
- Reproducible real HTTP smoke test with temporary SQLite (no real customer data).
- Website date defaults to Asia/Ho_Chi_Minh; docs and portfolio README.
- Render static demo Blueprint plus deployment and Android QA checklists.


## 2.0.0-alpha — 10/11/2026

- Thêm đăng nhập Admin/Staff cục bộ, tạo Admin lần đầu, quản trị nhân viên, đổi mật khẩu; schema v7.
- Bảo vệ 26 Activity trước bằng ProtectedActivity và RoleAccessPolicy.
- Thay luồng thanh toán quầy bằng một SQLite transaction nguyên tử và tách CheckoutRepository + CheckoutViewModel.
- Tách DashboardRepository + DashboardViewModel (LiveData + worker); cải thiện giao diện Material3 và ẩn tài chính với Staff.
- Thêm backend cloud pilot, website đặt sân, API chống trùng và bộ kiểm thử concurrency.
- Thêm adapter webhook ký HMAC, idempotency cho payment cloud; **chưa có bank/PSP merchant**.
- Thêm màn hình Android quản trị lịch cloud qua HTTPS; **không đồng bộ local SQLite ↔ cloud**.
- Android OS autoBackup tắt; backup thủ công vẫn chưa mã hóa.
- Có 8 backend tests + 39 Java pure method tests; Android APK chưa build do thiếu SDK/network.

# Changelog

## [1.2.0-dev] - 2026-11-10 (chưa phát hành, chưa build APK)

- Sửa phân loại bán hàng/cho thuê ở UI và tầng dữ liệu.
- Điều chỉnh gợi ý phí trễ, cộng dồn phí qua các lần trả từng phần, kiểm tra số lượng và chống overflow.
- Hỗ trợ hóa đơn có nhiều trang và hẹn giờ tắt đèn theo lượt đặt gần nhất mỗi sân.
- Kiểm tra lịch còn hiệu lực khi alarm nổ; cập nhật alarm cả hai sân khi chuyển lịch.
- Bổ sung 3 test JUnit mới và ghi chú về các bước QA bắt buộc.

## [1.1.0] - 2026-11-03

### Thêm mới

- Timeline trạng thái sân theo ngày, có điều hướng ngày trước/sau/hôm nay.
- Hiển thị cọc đang giữ trên Dashboard và thống kê thực thu/công nợ/cọc.
- Nút xem và khôi phục khách hàng đã ngừng hoạt động.
- Thao tác ngừng bán/mở bán lại dịch vụ.
- Unit test cho tính toán thuê thiết bị và xử lý thời gian qua 0h.

### Thay đổi

- Nâng database schema từ v4 lên v5 bằng migration bổ sung.
- Thêm cột `phien_choi.phuong_thuc_tt_moi` để lưu QR nội bộ, giữ tương thích cột cũ.
- Ghi nhận cọc thuê thiết bị vào bảng `thanh_toan`.
- Ghi nhận hoàn cọc/cấn trừ cọc khi trả thiết bị.
- Tính cọc đang giữ theo công thức COC - HOAN_COC - DIEU_CHINH.
- Sổ thanh toán hiển thị tổng net sau khi trừ hoàn cọc/điều chỉnh.
- Khách hàng có lịch sử đặt lịch được chuyển sang trạng thái ngừng thay vì chặn xóa.
- Dịch vụ đã phát sinh giao dịch được hướng dẫn ngừng bán thay vì báo lỗi chung.
- Chặn đặt lịch trùng phiên đang chơi, kể cả phiên qua 0h.
- Sao lưu lưu lại mốc thời gian gần nhất và kiểm tra toàn vẹn DB khi khôi phục.

### Sửa lỗi

- Tránh vi phạm CHECK constraint khi thanh toán bằng QR nội bộ.
- Sửa tổng sổ thanh toán bị cộng dương hoàn cọc.
- Bổ sung thông báo lỗi riêng cho trường hợp trùng phiên chơi.
- Timeline hiển thị phiên đang chơi từ ngày hôm trước.
