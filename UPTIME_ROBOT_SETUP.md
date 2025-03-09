# Thiết lập UptimeRobot để giữ cho Replit API luôn hoạt động

UptimeRobot là một dịch vụ giám sát thời gian hoạt động miễn phí sẽ ping trang web của bạn mỗi 5 phút, giúp giữ cho ứng dụng Replit của bạn luôn chạy. Dưới đây là hướng dẫn thiết lập:

## 1. Đăng ký tài khoản UptimeRobot

1. Truy cập [UptimeRobot](https://uptimerobot.com/) và đăng ký tài khoản miễn phí
2. Đăng nhập vào tài khoản của bạn

## 2. Tạo một Monitor mới

1. Nhấp vào nút "Add New Monitor"
2. Chọn "Monitor Type" là "HTTP(s)"
3. Đặt tên "Friendly Name" (ví dụ: "Novel Downloader API")
4. Nhập URL của ứng dụng Replit của bạn + đường dẫn ping:
   ```
   https://your-repl-name.your-username.repl.co/ping
   ```
5. Để "Monitoring Interval" ở mức 5 phút (tài khoản miễn phí)
6. Tùy chọn: Thiết lập thông báo qua email khi trang web của bạn không khả dụng
7. Nhấp vào "Create Monitor"

## 3. Xác minh thiết lập

1. Đợi vài phút cho lần ping đầu tiên
2. Kiểm tra bảng điều khiển UptimeRobot để xác nhận rằng nó đang ping ứng dụng của bạn thành công
3. Bạn sẽ thấy một dấu tích màu xanh lá cây và trạng thái "Up" nếu mọi thứ hoạt động chính xác

## 4. Tùy chọn: Thiết lập nhiều dịch vụ theo dõi

Để đảm bảo hơn nữa rằng ứng dụng của bạn luôn chạy, bạn có thể sử dụng nhiều dịch vụ theo dõi:

1. [Cron-job.org](https://cron-job.org/) - Một lựa chọn thay thế miễn phí khác
2. [Pingdom](https://www.pingdom.com/) - Một tùy chọn cao cấp hơn với nhiều tính năng
3. [StatusCake](https://www.statuscake.com/) - Cung cấp tùy chọn miễn phí tốt

## Lưu ý:

- Dịch vụ miễn phí của UptimeRobot cho phép tối đa 50 thiết bị theo dõi
- Khoảng thời gian ping được giới hạn ở mức tối thiểu 5 phút trong gói miễn phí
- Mặc dù điều này giúp giữ cho ứng dụng Replit của bạn chạy trong hầu hết các trường hợp, nó không đảm bảo thời gian hoạt động 100%
- Tùy chọn tốt nhất cho ứng dụng sản xuất là nâng cấp lên gói Replit Hacker hoặc sử dụng dịch vụ lưu trữ khác