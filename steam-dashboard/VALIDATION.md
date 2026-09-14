# Kết quả kiểm tra bộ code

Đã cài runtime requirements trong môi trường Python 3.12 và kiểm tra bằng Flask test client:
- Pipeline loại thiếu mã, mã trùng; giữ giá thiếu/NaN là NULL.
- Cùng bộ lọc: tổng số game ở games và stats bằng nhau.
- Lọc thể loại, giá miễn phí, thiếu giá, năm và kết quả rỗng.
- Phân trang và trả HTTP 400 cho giá âm, khoảng giá ngược, trang 0, NaN.
- CSV xuất toàn bộ kết quả, ngăn tên bắt đầu bằng công thức bảng tính.
- Header CORS và HTTP 503 khi thiếu database.

Kiểm tra dùng fixture giả lập, chưa dùng toàn bộ CSV Kaggle. Chưa kiểm thử trực quan trong trình duyệt hoặc đường hầm Ngrok thật; môi trường không tải được Chromium. Cần kiểm tra trên máy người dùng theo README. Ngrok cần tài khoản/token của người dùng, không có token trong gói code.
