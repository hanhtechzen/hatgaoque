# Hướng dẫn chạy trên máy có card NVIDIA (làm theo thứ tự)

Tổng thời gian lần đầu: khoảng **1–1,5 giờ**, phần lớn là chờ tải model. Các lần sau chỉ cần bước 6.

## ✅ Bước 0: Chuẩn bị
- Card NVIDIA, **tốt nhất từ 12 GB VRAM** (RTX 3060 12GB, 4060 Ti 16GB, 3090, 4070 trở lên...). Card 8 GB vẫn chạy nhưng chậm hơn.
- Ổ đĩa trống **từ 60 GB** (model AI khoảng 30 GB, cộng thư viện và video).
- Mạng ổn định (lần đầu tải nhiều).

## ✅ Bước 1: Cập nhật driver card
Tải driver mới nhất: https://www.nvidia.com/Download/index.aspx, cài rồi **khởi động lại máy**.
Kiểm tra: mở PowerShell, gõ `nvidia-smi`. Thấy tên card và bảng thông số là được.

## ✅ Bước 2: Cài Python
Tải **Python 3.12 hoặc 3.13** tại https://www.python.org/downloads/. Khi cài **tick "Add python.exe to PATH"**.

## ✅ Bước 3: Lấy source
```powershell
git clone https://github.com/hanhtechzen/hatgaoque.git
```
Không có Git: vào trang GitHub → **Code → Download ZIP** → giải nén, ví dụ vào `D:\hatgaoque`.
Đã có source cũ: mở PowerShell trong thư mục đó rồi gõ `git pull`.

## ✅ Bước 4: Cài đặt cơ bản
Nhấp đúp **`setup.bat`** và chờ đến khi hiện "XONG".

## ✅ Bước 5: Bật GPU
Nhấp đúp **`setup-gpu.bat`**. Script sẽ:
1. Hiện tên card và VRAM.
2. Cài PyTorch bản CUDA (khoảng 3 GB).
3. Cài thư viện AI.
4. **Tạo thử 1 ảnh và 1 clip** (lần đầu tải model khoảng 20–30 GB, có thể mất 30–60 phút).

Xong thì mở thư mục **`output\gpu_test\`**:
- `anh_thu.jpg`: Bin chạy với con diều, bà đứng ở cổng.
- `clip_thu.mp4`: clip cử động 4 giây.

## ✅ Bước 6: Mở trang quản lý
Nhấp đúp **`start_web.bat`**, trình duyệt sẽ mở http://127.0.0.1:8686.
1. **⚙️ Cài đặt** → dán **Pollinations key** → Lưu. Key vẫn cần cho giọng MAI và AI viết kịch bản.
2. **🏠 Tổng quan** → ô **🖥️ card đồ họa** phải hiện tên card.
3. Bấm **▶ Tạo 1 video ngay** → theo dõi ở **📋 Tác vụ**. Video đầu chậm vì nạp model; các video sau nhanh hơn.

## 📤 Gửi lại cho Claude để tinh chỉnh
Gửi giúp mình:
1. **Tên card và VRAM** (dòng đầu khi chạy `setup-gpu.bat`).
2. Ảnh `anh_thu.jpg` và clip `clip_thu.mp4`.
3. Nếu lỗi: **chụp màn hình cửa sổ đen**, hoặc copy file log mới nhất trong thư mục `logs\`.
4. Thời gian tạo 1 video (xem trong tab Tác vụ).

## 🆘 Lỗi thường gặp
| Hiện tượng | Cách xử lý |
|---|---|
| `nvidia-smi` không chạy | Cài lại driver NVIDIA, khởi động lại máy |
| "torch không thấy card NVIDIA" | Chạy lại `setup-gpu.bat` (có thể đã cài nhầm torch bản CPU) |
| `CUDA out of memory` | Trong `config.json`, phần `gpu`, thêm `"video_width": 384, "video_height": 672`; hoặc giảm `motion.max_shots_local` xuống 3 |
| Tải model rất chậm hoặc đứt | Chạy lại `setup-gpu.bat`, model tải tiếp từ chỗ dở |
| Clip cử động bị méo mặt | Bình thường ở vài cảnh; mô tả cử động (ô "Cử động" trong Kịch bản) nhẹ nhàng hơn sẽ đỡ |
