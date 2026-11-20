# 🌾 Hạt Gạo Quê Studio

Tool tự động làm **phim hoạt hình 3D ngắn (9:16, ~25–30 giây)** về tuổi thơ 8x 9x ở làng quê Việt Nam, với bé **Bin** và **ông bà**. Đăng lên **Facebook Reels** và **TikTok**, có trang web quản lý bằng chuột.

```
Kịch bản ─► Giọng đọc ─► Ảnh 3D giữ đúng nhân vật ─► Cảnh cử động ─► Dựng video ─► Đăng & tăng trưởng
(AI viết     (VieNeu trên   (Pollinations: z-image      (Seedance,     (FFmpeg: phụ đề   (FB tự đăng, TikTok
 theo mùa)    máy + MAI)     + FLUX Klein theo ảnh mẫu)  tùy chọn)      CapCut, nhạc,     hàng chờ, AI trả lời
                                                                        cảnh kết)          bình luận, xếp hạng)
```

**Chi phí:** khoảng 0–1.000đ/video nếu chỉ dùng ảnh (phần miễn phí hằng ngày của Pollinations thường đủ). Khoảng 4.000–5.000đ/video nếu bật cảnh cử động. Tool tự giới hạn theo ngân sách bạn đặt.

---

## 1. Cài đặt (Windows, làm 1 lần)

**Yêu cầu:** Windows 10/11, khoảng 5 GB ổ trống, có Internet. Không cần card đồ họa.

1. **Cài Python 3.12 trở lên:** tải tại https://www.python.org/downloads/. Khi cài, **tick "Add python.exe to PATH"**.
2. **Tải source về máy**, chọn một trong hai cách:
   - Có Git:
     ```powershell
     git clone https://github.com/hanhtechzen/hatgaoque.git
     ```
   - Không có Git: trên trang GitHub bấm **Code → Download ZIP**, rồi giải nén.
3. **Nhấp đúp `setup.bat`**. Tool tự tạo môi trường Python, cài thư viện và tạo file `.env`. Lần đầu mất vài phút.
4. **Nhấp đúp `start_web.bat`**. Trình duyệt mở **http://127.0.0.1:8686**. Trang chỉ mở được trên chính máy này.
5. Vào tab **⚙️ Cài đặt**, dán **Pollinations key** (xem mục 2), bấm **Lưu**, rồi bấm **🩺 Kiểm tra**.

> Lần đầu tạo video, tool tự tải model giọng đọc VieNeu (khoảng vài trăm MB). Các lần sau chạy ngay.

### 1b. Máy có card NVIDIA? Bật chế độ GPU (khuyên dùng)

📄 **Hướng dẫn từng bước: [HUONG_DAN_GPU.md](HUONG_DAN_GPU.md)**

Nhấp đúp **`setup-gpu.bat`** (sau khi đã chạy `setup.bat`). Script tự cài PyTorch bản CUDA và thư viện AI, rồi **tạo thử 1 ảnh + 1 clip** vào `output\gpu_test\`. Lần đầu tải model khoảng 20–30 GB.

Bật GPU xong thì tool tự dùng card, không cần chỉnh gì:

| Phần | Không GPU | Có GPU |
|---|---|---|
| Ảnh | Pollinations (online) | **SDXL + IP-Adapter trên máy**: giữ đúng mặt Bin/ông/bà theo ảnh mẫu, 0đ |
| Cảnh cử động | Seedance, ~1.000đ/clip, tối đa 3 cảnh | **LTX-Video trên máy: tối đa 6 cảnh/video, clip dài vừa câu thoại, 0đ** |
| Phụ đề | Whisper `small` (CPU) | Whisper `large-v3-turbo` (GPU), khớp từng chữ chính xác hơn |

- Card **từ 12 GB VRAM** chạy thoải mái. Card 8 GB tự giảm độ phân giải clip và chạy tiết kiệm VRAM (chậm hơn).
- Card lớn (24 GB trở lên) muốn clip đẹp hơn: trong `config.json` đổi `gpu.video_model` thành `Wan-AI/Wan2.1-I2V-14B-480P-Diffusers`.
- Lỗi GPU ở cảnh nào thì cảnh đó tự lùi về ảnh tĩnh hoặc Pollinations, video vẫn ra.
- Trang quản lý → Tổng quan có ô **🖥️ card đồ họa** và link **chạy thử**.

## 2. Các key cần có

| Key | Bắt buộc? | Dùng để | Lấy ở đâu |
|---|---|---|---|
| `POLLINATIONS_TOKEN` | **Có** | Ảnh 3D, giọng MAI, AI viết kịch bản, cảnh cử động, nhạc AI | https://enter.pollinations.ai → đăng nhập → tạo key. Nạp thêm tiền nếu muốn cảnh cử động hoặc nhạc AI |
| `FB_PAGE_ID`, `FB_PAGE_TOKEN` | Không | Tự đăng Reels, bình luận đầu, lấy số liệu, trả lời bình luận | Xem mục 6 |
| `GEMINI_API_KEY` | Không | Dự phòng cho AI viết kịch bản | https://aistudio.google.com/apikey |

Key được lưu trong file `.env` ở máy bạn. File này **không bao giờ được đưa lên GitHub** (đã có trong `.gitignore`).

## 3. Dùng trang quản lý

| Tab | Làm gì |
|---|---|
| 🏠 **Tổng quan** | **Tạo 1 video ngay** / **Tạo trước 7 video**; danh sách việc cần làm |
| 🚀 **Tăng trưởng** | Chiến lược đăng (số video/ngày, khung giờ), **hàng chờ TikTok**, **bình luận chờ trả lời** (AI soạn sẵn), **bảng xếp hạng** video |
| 🎬 **Video** | Xem, copy nội dung đăng, tải về, đăng Facebook, lưu trữ |
| 📝 **Kịch bản** | Sửa từng cảnh (lời kể, lời thoại ông/bà, mô tả ảnh, cử động), **AI viết** theo chủ đề, **Dựng video** |
| 💡 **Chủ đề** | Kho chủ đề để AI tự viết khi hết kịch bản |
| 🧒 **Nhân vật** | Ảnh mẫu Bin, ông, bà...; sửa mô tả rồi **Vẽ lại** |
| 🎙️ **Giọng đọc** | Chọn giọng người kể, bà, ông; **Nghe thử** |
| 🎵 **Âm thanh** | Tải nhạc nền và âm thanh không khí lên, hoặc **Tạo bằng AI** (khoảng 14.600đ, tạo 1 lần) |
| ⚙️ **Cài đặt** | Key, ngân sách mỗi video, cảnh cử động, cảnh kết, Facebook, **lịch chạy tự động mỗi ngày** |
| 📋 **Tác vụ** | Tiến độ và log các việc đang chạy, nút hủy |

## 4. Chạy tự động mỗi ngày

Vào tab **⚙️ Cài đặt → ⏰ Chạy tự động mỗi ngày**, tick **Bật**, chọn giờ, bấm **Áp dụng**. Mỗi ngày tới giờ đó máy sẽ:
1. Tạo video (số lượng theo tab Tăng trưởng, mặc định 2), ưu tiên chủ đề đúng mùa.
2. Hẹn giờ đăng Facebook (mặc định 11:30 và 19:30) và tự đăng bình luận đầu.
3. Lấy số liệu và bình luận mới; AI soạn sẵn câu trả lời để bạn duyệt.

Máy cần bật và đã đăng nhập Windows. Nếu máy tắt đúng giờ, lần chạy sẽ bù khi máy mở lại.

## 5. Chiến lược tăng trưởng

| Đòn bẩy | Tool tự làm | Bạn làm |
|---|---|---|
| Đăng đều | 2 video/ngày, tự hẹn giờ Facebook | Không cần làm gì |
| Đúng mùa | Ưu tiên tập Tết, Trung thu, khai giảng, 20/11, mùa hè... theo `data/calendar.json` | Mỗi năm sửa lại ngày Tết, Trung thu âm lịch |
| Kéo bình luận | Bình luận đầu là câu hỏi; AI soạn trả lời mọi bình luận mới | Bấm **Gửi**, hoặc bật tự gửi |
| Mời theo dõi | Cảnh kết: Bin vẫy tay + "Theo dõi HẠT GẠO QUÊ để xem tập sau" | Không cần làm gì |
| TikTok | Hàng chờ có giờ gợi ý, nút copy nội dung | Khoảng 1 phút/video trên TikTok Studio |
| Học từ tập thắng | Xếp hạng FB + TikTok; AI viết tập mới theo kiểu 5 tập dẫn đầu | Nhập lượt xem TikTok vào bảng |

**Không dùng:** mua view/follow, bot follow/like/comment dạo, tool đăng TikTok không chính thức. Những cách này làm kênh bị bóp tương tác, bị khóa hoặc mất quyền kiếm tiền.

## 6. Kết nối Facebook Page

1. Vào https://developers.facebook.com → **My Apps → Create App**, chọn use case quản lý Page.
2. Mở **Graph API Explorer**, chọn app vừa tạo, bấm **Get User Access Token** với các quyền:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_manage_engagement`, `read_insights`.
3. Dán token vào **Access Token Debugger** → bấm **Extend Access Token** để được token dài hạn.
4. Trong Graph API Explorer, dùng token dài hạn gọi `me/accounts`. Lấy `id` và `access_token` của Page. Page token lấy theo cách này không hết hạn.
5. Dán vào trang quản lý: **⚙️ Cài đặt** → Facebook Page ID / Token → tick **Tự đăng lên Facebook Page** → **Lưu** → **🩺 Kiểm tra**.

Nếu bài đăng chỉ mình bạn thấy, chuyển app sang chế độ **Live** trong trang quản lý app.

## 7. TikTok

TikTok chỉ cho tool tự đăng sau khi app được TikTok kiểm duyệt. Vì vậy dùng **hàng chờ TikTok** trong tab 🚀 Tăng trưởng:
**Copy nội dung → Mở TikTok Studio → kéo video vào → dán nội dung → hẹn giờ theo gợi ý → bấm "Đã đăng"**.
Nhớ bật nhãn **"Nội dung do AI tạo"** khi đăng.

## 8. Dùng bằng dòng lệnh (tùy chọn)

```powershell
.venv\Scripts\python.exe -m studio <lệnh>
```

| Lệnh | Việc làm |
|---|---|
| `web` | Mở trang quản lý |
| `run [--count N] [--no-post]` | Tạo N video, lên lịch Facebook |
| `make <id hoặc file.json>` | Dựng video từ một kịch bản |
| `write "<chủ đề>"` | AI viết kịch bản mới, lưu vào `data/scripts` |
| `characters [BIN BA ONG]` | Vẽ lại ảnh mẫu nhân vật |
| `outro` | Tạo ảnh cảnh kết |
| `sample <vieneu/mai/edge> "<giọng>" <file.wav>` | Tạo file nghe thử một giọng |
| `audio-ai [--only music/sfx]` | AI tạo nhạc nền và âm thanh không khí |
| `post <thư mục output>` | Đăng một video lên Facebook |
| `sync` | Lấy số liệu và bình luận Facebook |
| `gpu-test` | Kiểm tra card NVIDIA, tạo thử ảnh + clip |
| `check` / `status` | Kiểm tra cài đặt / xem danh sách video |

## 9. Cấu trúc thư mục

```
hatgaoque/
├─ setup.bat, start_web.bat     cài đặt / mở trang quản lý
├─ setup-gpu.bat                bật chế độ GPU (card NVIDIA)
├─ run_daily.bat                 việc chạy mỗi ngày (Task Scheduler gọi)
├─ register_task.ps1             đăng ký lịch Windows
├─ config.json                   mọi cài đặt (trang web sửa giúp)
├─ .env.example                  mẫu file key (.env thật nằm ở máy, không lên git)
├─ studio/                       mã nguồn Python
│  ├─ __main__.py                các lệnh
│  ├─ script_gen.py              lấy / nhờ AI viết kịch bản
│  ├─ tts.py                     giọng đọc (VieNeu, MAI, edge-tts)
│  ├─ images.py                  ảnh 3D, ảnh mẫu nhân vật, tông màu
│  ├─ motion.py                  cảnh cử động (GPU trên máy hoặc Seedance)
│  ├─ local_gpu.py               AI chạy trên card NVIDIA (SDXL, LTX-Video)
│  ├─ align.py                   khớp phụ đề từng chữ bằng Whisper
│  ├─ video.py                   dựng video, phụ đề, âm thanh
│  ├─ outro.py                   cảnh kết mời theo dõi
│  ├─ growth.py                  lịch theo mùa, số liệu, bình luận, xếp hạng
│  ├─ facebook.py                Graph API (đăng, bình luận, số liệu)
│  ├─ audio_ai.py                AI tạo nhạc và âm thanh
│  ├─ polli.py                   gọi Pollinations
│  └─ web.py                     server trang quản lý
├─ web/                          giao diện (HTML/CSS/JS)
├─ data/
│  ├─ scripts/*.json             kịch bản (mỗi tập một file)
│  ├─ characters.json            mô tả nhân vật
│  ├─ topics.txt                 kho chủ đề
│  └─ calendar.json              mùa nội dung
├─ assets/
│  ├─ characters/                ảnh mẫu Bin, ông, bà
│  ├─ outro/                     ảnh cảnh kết
│  ├─ music/, sfx/               nhạc nền, âm thanh không khí (tự thêm)
│  └─ images/<id>/               ảnh thật thay ảnh AI (tùy chọn)
└─ output/                       video đã tạo (không lên git)
```

## 10. Xử lý lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `python` không chạy được | Cài lại Python và tick **Add to PATH** |
| Cảnh cử động báo `402 INSUFFICIENT_BALANCE` | Nạp tiền Pollinations, hoặc tắt "Cảnh cử động" trong Cài đặt. Video vẫn ra bằng ảnh tĩnh |
| Lỗi SSL / certificate | Đã tự xử lý bằng `truststore`; nếu vẫn lỗi, kiểm tra phần mềm diệt virus hoặc proxy |
| Ảnh vẽ sai nhân vật | Vào tab Nhân vật sửa mô tả và **Vẽ lại**. Trong kịch bản không tả lại quần áo nhân vật |
| Trang web không mở | Đóng cửa sổ `start_web.bat` cũ rồi mở lại; xem lỗi trong cửa sổ đen |

## Lưu ý

- Nhạc và âm thanh: chỉ dùng nhạc miễn bản quyền (Pixabay) hoặc nhạc AI tạo trong tool.
- Caption tự ghi chú ảnh do AI tạo (sửa ở `ai_note` trong `config.json`).
- Giữ bí mật file `.env`. Nếu lỡ lộ key, vào trang Pollinations / Facebook xóa key cũ và tạo key mới.
