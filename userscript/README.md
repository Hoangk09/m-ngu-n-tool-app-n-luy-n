# Quiz Solver Userscript - Hướng Dẫn Sử Dụng

## Cài Đặt

### Bước 1: Cài Tampermonkey
1. Cài extension Tampermonkey từ Chrome Web Store
2. Hoặc dùng Violentmonkey (tương tự)

### Bước 2: Cài Userscript
1. Mở file `quiz-solver.user.js` trong trình soạn thảo
2. Copy toàn bộ nội dung
3. Mở Tampermonkey Dashboard
4. Click "Create new script"
5. Paste nội dung vào
6. Ctrl+S để lưu

### Bước 3: Truy Cập onluyen.vn
1. Vào https://app.onluyen.vn
2. Panel "🤖 Quiz Solver" sẽ xuất hiện góc phải màn hình

## Sử Dụng

### Cấu Hình Lần Đầu
1. Click ⚙️ "Cài Đặt"
2. Nhập Gemini API Key (nếu có)
   - Để trống nếu dùng Gemini Web
3. Chọn Gemini Model
4. Điều chỉnh Delay (khuyến nghị: 3-8 giây)
5. Click "Lưu"

### Giải Quiz
1. Mở bất kỳ bài quiz nào trên onluyen.vn
2. Click ▶️ "BẮT ĐẦU GIẢI"
3. Userscript sẽ tự động:
   - phát
 hiện câu hỏi
   - Gọi Gemini AI
   - Chọn đáp án
   - Chuyển câu tiếp theo

### Dừng Lại
- Click ⏹️ "DỪNG LẠI" bất cứ lúc nào

## Tính Năng

- ✅ Auto-solve trắc nghiệm
- ✅ Hỗ trợ câu trả lời ngắn
- ✅ Hỗ trợ Đúng/Sai
- ✅ Gemini AI integration
- ✅ Floating UI không che view
- ✅ Logs real-time
- ✅ Có thể minimize

## Lưu Ý

- **Không cần Chrome Extension** - Chỉ cần Tampermonkey
- **Tương thích** - Hoạt động giống hệt extension
- **Nhẹ** - Một file duy nhất
- **Dễ update** - Chỉnh sửa trực tiếp trong Tampermonkey

## Troubleshooting

### Panel không hiện
- Kiểm tra Tampermonkey đã bật chưa
- Refresh lại trang onluyen.vn

### Không giải được quiz
- Kiểm tra đã cấu hình API key hoặc đã login Gemini
- Xem logs để biết lỗi cụ thể

### Cần support
- Check console (F12) để xem errors
- Liên hệ team support
