# BTL_ATTT

# 1. Tổng quan dự án

Đây là hệ thống chia thành hai server **Upload** và **Download**, dùng để upload, lưu trữ, tải về file MP3 một cách bảo mật (mã hóa, xác thực bằng RSA + AES + chữ ký số).

# **2. Cấu trúc thư mục chuẩn của dự án**
---
/project-root/
├── main.py
├── upload_server.py
├── download_server.py
├── start_upload_server.py
├── start_download_server.py
├── style.css
├── /templates/
│   ├── index.html
│   ├── upload.html
│   └── download.html
├── /uploads/
│   └── ... (các file mp3 đã upload)
├── /downloads/
│   └── ... (các file tải về)
├── /keys/
│   ├── server_private.pem
│   ├── server_public.pem
│   ├── client_private.pem
│   └── client_public.pem
├── /shared_data/
│   └── file_registry.json
├── users.json           # Lưu user (nếu có)
├── files.json           # Lưu file (nếu có)
└── README.md            # (Tùy chọn, mô tả dự án)
----
# 3. Cách hoạt động tổng thể

1. Người dùng tạo User ID (trên trang upload)
   → Tự sinh cặp RSA Key.
2. Upload file MP3
   → File được mã hóa bằng AES, key AES lại được mã hóa bằng RSA Public Key của User.
3. Nhận encryption data & public key
   → Chia sẻ public key + encryption data để người khác có thể tải file và giải mã.
4. Download file
   → Người nhận nhập đúng public key và encryption data, file được xác thực chữ ký, giải mã bằng private key.
5. Tất cả thao tác này đều qua giao diện web (HTML đặt trong /templates/)**

# 4. Hướng dẫn khởi chạy

## Bước 1: Đặt file HTML vào đúng thư mục

Tạo thư mục `/templates/` trong thư mục dự án, copy các file sau vào:

* `index.html`
* `upload.html`
* `download.html`

## Bước 2: Chạy server

Chạy Upload Server:

  
  python start_upload_server.py
  

  Mặc định chạy trên [http://localhost:3000](http://localhost:3000) 

* **Chạy Download Server:**

  python start_download_server.py

   Mặc định chạy trên [http://localhost:3000](http://localhost:3000) 

![image](https://github.com/user-attachments/assets/5803ff15-2dd5-4710-9775-b38f02b44c18)
