# AITele Cloudflare Pages — giao diện tiếng Việt kết nối API thực

Ứng dụng ở thư mục `web/` dùng **Pages Functions** gọi tới API của MTDS qua URL cố định `https://telecom.mtds.vn/api/v1/`. Không dùng dữ liệu mẫu; mọi thao tác tạo cuộc gọi, trợ lý và kho kiến thức được gửi đến dịch vụ thực. Repository gốc là **Python SDK**, không chứa mã nguồn tổng đài MTDS, STT, TTS hoặc SIP.

## Cloudflare Pages

- Project: `aitele`
- Địa chỉ: https://aitele.pages.dev
- GitHub: `xulytiengviet/aitele`, branch `cloudflare-pages`
- Root directory: `/`
- Build command: **để trống**
- Build output directory: `web` (Pages Functions nằm ở `web/functions/`)
- Preview deployments: tắt để tránh môi trường preview có thể phát sinh cuộc gọi thật.

## Secrets bắt buộc

Trong **Cloudflare Dashboard → Workers & Pages → aitele → Settings → Variables and Secrets → Production**, thêm:

| Tên | Loại | Giá trị |
|---|---|---|
| `AI_TELECOM_API_KEY` | Secret | API key hợp lệ được cấp bởi MTDS |
| `DASHBOARD_PASSWORD` | Secret | Mật khẩu quản trị đủ mạnh, riêng cho dashboard |
| `SESSION_SECRET` | Secret | Chuỗi ngẫu nhiên 32 byte trở lên, ví dụ `openssl rand -hex 32` |

**Không gửi các khóa lên GitHub, không lưu trong frontend.** Cấu hình Cloudflare Access bảo vệ toàn website và giới hạn quyền truy cập theo email; trang đăng nhập hiện tại bổ sung một lớp bảo vệ nhưng không thay thế Access, MFA và hạn chế tốc độ. Sau khi lưu Secrets, triển khai lại.

## Chức năng đã viết

- Dashboard lấy số liệu thật từ `GET /usage`, `GET /calls`, `GET /agents`.
- Tạo/sửa/xóa trợ lý AI; chọn giọng, tốc độ, kịch bản và kho kiến thức.
- Gọi điện thật qua `POST /calls` **sau khi người dùng xác nhận**. Hủy cuộc gọi; xem transcript, score, outcome, summary và lấy liên kết ghi âm có thời hạn.
- Quản lý kho kiến thức và tài liệu văn bản/file (UI giới hạn 10 MB).
- Xem số điện thoại được cấp và mức sử dụng.
- Reverse proxy có allowlist endpoint, khóa truy cập chỉ lưu server-side, session cookie HttpOnly + Secure + SameSite, kiểm tra Origin cho mọi POST/PATCH/DELETE.

**Điều kiện để gọi điện thực:** khóa MTDS có quyền gọi, tài khoản có số điện thoại/SIP được cấp và hạn mức hợp lệ. Cloudflare Pages không thể cấp số hay vận hành mô hình âm thanh thay nhà cung cấp. Repository này không chứa các thành phần đó.

## Kiểm tra trước khi đưa vào sử dụng

1. Truy cập `/api/auth/status`, xác nhận `configured:true` sau khi thêm API key.
2. Đăng nhập, mở Trợ lý AI và tạo 1 Agent; tải lại và kiểm tra hiển thị từ API.
3. Tạo kho kiến thức, thêm tài liệu, kiểm tra trạng thái `ready`.
4. Kiểm tra Số điện thoại và hạn mức tài khoản.
5. Thử cuộc gọi đến số của chính bạn hoặc số có sự đồng ý rõ ràng; xem tiến trình và transcript/ghi âm.
6. Bật Cloudflare Access và bảo vệ dữ liệu cá nhân, bổ sung danh sách không liên hệ và kiểm tra khung giờ theo chính sách áp dụng.

## Lưu ý về phạm vi

Mẫu này kết nối chức năng thật trong SDK; **không phải bản sao toàn bộ MTDS**. Những chức năng không được API hiện tại cung cấp (cấp số, quản trị SIP, nhận cuộc gọi đến, cài đặt giọng TTS ở cấp hạ tầng, realtime streaming) cần API khác hoặc hạ tầng bên thứ ba. Chi phí và trạng thái chỉ phản ánh dữ liệu API trả về.
