
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import base64
import hashlib
import json
import os
import time
import requests
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

app = Flask(__name__)
app.config['SECRET_KEY'] = 'upload_server_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# URL của download server
DOWNLOAD_SERVER_URL = "http://192.168.1.100:5001"  # Thay đổi IP theo máy download server

# Tạo thư mục lưu trữ
os.makedirs('uploads', exist_ok=True)
os.makedirs('keys', exist_ok=True)
os.makedirs('shared_data', exist_ok=True)

def generate_rsa_keypair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
    )
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_key, public_key, private_pem, public_pem

# Khởi tạo keys
server_private_key, server_public_key, server_private_pem, server_public_pem = generate_rsa_keypair()
client_private_key, client_public_key, client_private_pem, client_public_pem = generate_rsa_keypair()

# Lưu keys vào file
with open('keys/server_private.pem', 'wb') as f:
    f.write(server_private_pem)
with open('keys/server_public.pem', 'wb') as f:
    f.write(server_public_pem)
with open('keys/client_private.pem', 'wb') as f:
    f.write(client_private_pem)
with open('keys/client_public.pem', 'wb') as f:
    f.write(client_public_pem)

class SecureFileHandler:
    def __init__(self):
        self.uploaded_files = {}
        self.load_shared_data()
        
    def load_shared_data(self):
        try:
            if os.path.exists('shared_data/file_registry.json'):
                with open('shared_data/file_registry.json', 'r') as f:
                    self.uploaded_files = json.load(f)
        except:
            self.uploaded_files = {}
    
    def save_shared_data(self):
        try:
            with open('shared_data/file_registry.json', 'w') as f:
                json.dump(self.uploaded_files, f, indent=2)
            
            # Đồng bộ với download server
            self.sync_with_download_server()
        except Exception as e:
            print(f"Error saving shared data: {e}")
    
    def sync_with_download_server(self):
        try:
            # Gửi dữ liệu đến download server
            requests.post(f"{DOWNLOAD_SERVER_URL}/sync_data", 
                         json=self.uploaded_files,
                         timeout=5)
        except:
            print("Could not sync with download server")
        
    def encrypt_file(self, file_data, session_key):
        nonce = get_random_bytes(12)
        cipher = AES.new(session_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(file_data)
        return nonce, ciphertext, tag
    
    def decrypt_file(self, nonce, ciphertext, tag, session_key):
        cipher = AES.new(session_key, AES.MODE_GCM, nonce=nonce)
        try:
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return plaintext
        except ValueError:
            return None
    
    def sign_metadata(self, metadata, private_key):
        metadata_json = json.dumps(metadata, sort_keys=True)
        signature = private_key.sign(
            metadata_json.encode(),
            padding.PKCS1v15(),
            hashes.SHA512()
        )
        return base64.b64encode(signature).decode()
    
    def verify_signature(self, metadata, signature, public_key):
        try:
            metadata_json = json.dumps(metadata, sort_keys=True)
            signature_bytes = base64.b64decode(signature)
            public_key.verify(
                signature_bytes,
                metadata_json.encode(),
                padding.PKCS1v15(),
                hashes.SHA512()
            )
            return True
        except:
            return False
    
    def decrypt_session_key(self, encrypted_key, private_key):
        try:
            encrypted_key_bytes = base64.b64decode(encrypted_key)
            session_key = private_key.decrypt(
                encrypted_key_bytes,
                padding.PKCS1v15()
            )
            return session_key
        except:
            return None

file_handler = SecureFileHandler()

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload')
def upload_page():
    return render_template('upload.html')

@app.route('/get_public_key')
def get_public_key():
    return jsonify({
        'public_key': server_public_pem.decode(),
        'client_public_key': client_public_pem.decode()
    })

@socketio.on('handshake')
def handle_handshake():
    emit('handshake_response', {'message': 'Upload Server Ready!'})

@socketio.on('upload_file')
def handle_upload(data):
    try:
        # Lấy session key trực tiếp (đã là base64)
        session_key = base64.b64decode(data['encrypted_session_key'])
        
        # Verify metadata (simplified)
        metadata = data['metadata']
        
        # Giải mã dữ liệu
        nonce = base64.b64decode(data['nonce'])
        ciphertext = base64.b64decode(data['cipher'])
        tag = base64.b64decode(data['tag'])
        
        # Kiểm tra dữ liệu
        if len(ciphertext) == 0:
            emit('upload_error', {'error': 'Không có dữ liệu file'})
            return
        
        # Kiểm tra định dạng file
        filename = metadata['filename']
        if not filename.lower().endswith('.mp3'):
            emit('upload_error', {'error': 'Chỉ cho phép file MP3'})
            return
        
        # Sử dụng dữ liệu file trực tiếp (đã mã hóa)
        file_data = ciphertext
        
        # Lưu file với tên an toàn
        safe_filename = os.path.basename(filename)  # Ngăn chặn path traversal
        file_path = os.path.join('uploads', safe_filename)
        
        try:
            with open(file_path, 'wb') as f:
                f.write(file_data)
        except Exception as e:
            emit('upload_error', {'error': f'Lỗi lưu file: {str(e)}'})
            return
        
        # Lưu thông tin file
        file_handler.uploaded_files[safe_filename] = {
            'metadata': metadata,
            'session_key': base64.b64encode(session_key).decode(),
            'upload_time': datetime.now().isoformat(),
            'server_ip': request.remote_addr,
            'file_size': len(file_data)
        }
        
        # Đồng bộ dữ liệu
        file_handler.save_shared_data()
        
        print(f"✅ File uploaded: {safe_filename} ({len(file_data)} bytes)")
        
        emit('upload_success', {
            'message': 'Upload thành công!', 
            'filename': safe_filename,
            'session_key': base64.b64encode(session_key).decode(),
            'key_message': '🔑 Lưu key này để download và giải mã file!',
            'file_size': len(file_data)
        })
        
    except Exception as e:
        emit('upload_error', {'error': str(e)})

@app.route('/list_files')
def list_files():
    files = []
    for filename, info in file_handler.uploaded_files.items():
        files.append({
            'filename': filename,
            'size': info['metadata']['size'],
            'upload_time': info['upload_time']
        })
    return jsonify(files)

@app.route('/get_file/<filename>')
def get_file(filename):
    try:
        file_path = os.path.join('uploads', filename)
        if os.path.exists(file_path) and filename in file_handler.uploaded_files:
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Upload Server starting on port 5000...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
