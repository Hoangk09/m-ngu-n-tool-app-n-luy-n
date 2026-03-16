# Quiz Solver Android App - Full Version

## Cấu trúc files

```
android_app/
├── main.py                    # Main Kivy app + Floating panel
├── solver.py                  # Gemini API integration  
├── accessibility.py           # Python bridge to Java service
├── buildozer.spec             # Build configuration
├── java/
│   └── org/nhat/quizsolver/
│       └── QuizAccessibilityService.java  # Java Accessibility Service
├── res/
│   ├── xml/
│   │   └── accessibility_service_config.xml
│   └── values/
│       └── strings.xml
├── templates/
│   └── AndroidManifest.tmpl.xml
└── README.md
```

## Tính năng đầy đủ

### 1. Floating Overlay Panel
- Kích thước 300x220px
- Draggable (kéo thả tự do)
- Minimize (thu nhỏ thành 60x60)
- Nút BẮT ĐẦU / DỪNG
- Hiển thị trạng thái real-time
- Counter số câu đã giải
- Nút Cài đặt & Accessibility

### 2. Gemini Web Integration
- Đăng nhập bằng cookie __Secure-1PSID
- Không cần API key
- Hỗ trợ model 2.5-flash và 2.5-pro
- Parse response tự động

### 3. Accessibility Service (Java)
- Đọc toàn bộ UI từ app Ôn Luyện
- Tìm câu hỏi (text dài nhất)
- Tìm đáp án A, B, C, D
- Thực hiện click gesture
- Swipe sang câu tiếp theo
- Tìm và click nút "Tiếp"

## Build

### Yêu cầu
- Ubuntu/WSL với Python 3.11
- Buildozer
- Android SDK/NDK

### Steps

```bash
cd ~/android_app

# Copy toàn bộ thư mục từ Windows
# Bao gồm: main.py, solver.py, accessibility.py, buildozer.spec
# Và thư mục: java/, res/, templates/

# Xóa cache cũ hoàn toàn
rm -rf .buildozer

# Build
buildozer android debug

# APK sẽ ở: bin/quizsolver-1.0.3-arm64-v8a-debug.apk
```

### Install

```bash
adb install bin/quizsolver-1.0.3-arm64-v8a-debug.apk
```

## Cách sử dụng

### Bước 1: Cấp quyền
1. Mở app Quiz Solver
2. Nhấn **Accessibility** → Bật "Quiz Solver" trong Settings
3. Cho phép **"Display over other apps"** nếu được hỏi

### Bước 2: Đăng nhập Gemini
1. Nhấn **Cài đặt**
2. Mở Gemini trong browser, đăng nhập Google
3. Copy cookie `__Secure-1PSID` từ DevTools
4. Dán vào app và Lưu

### Bước 3: Chạy
1. Mở app **Ôn Luyện**
2. Vào bài quiz
3. Nhấn **BẮT ĐẦU** trên floating panel
4. App sẽ tự động:
   - Đọc câu hỏi từ UI
   - Gửi lên Gemini để lấy đáp án
   - Click vào đáp án đúng
   - Chuyển câu tiếp theo
5. Nhấn **DỪNG** để tạm dừng

## Lưu ý quan trọng

### Accessibility Service
- Cần Android 7.0+ (API 24) để sử dụng gesture
- Service phải được bật thủ công trong Settings
- Chỉ hoạt động khi app Ôn Luyện đang mở

### Gemini
- Cookie có thể hết hạn sau vài tuần
- Cần đăng nhập lại nếu bị lỗi
- Rate limit có thể xảy ra nếu giải quá nhanh

### Floating Panel
- Panel nằm trong app Quiz Solver
- Khi minimize app, panel sẽ ẩn
- Cần để app Quiz Solver chạy background

## Troubleshooting

### App crash khi mở
- Check logcat: `adb logcat | grep -i python`
- Xóa cache và build lại

### Accessibility không tìm thấy câu hỏi
- Đảm bảo đang ở màn hình quiz của Ôn Luyện
- Nhấn rescan (trong code)
- Check package name của Ôn Luyện

### Gemini không trả lời
- Kiểm tra cookie còn hợp lệ
- Thử đăng nhập lại
- Check kết nối internet

## Permissions

| Permission | Mục đích |
|------------|----------|
| INTERNET | Gọi Gemini API |
| SYSTEM_ALERT_WINDOW | Floating overlay |
| BIND_ACCESSIBILITY_SERVICE | Đọc UI và click |
