import os
import time
import subprocess
import threading
import json
import shutil
import uuid
import re  # เพิ่ม regex สำหรับตรวจสอบชื่อไฟล์
from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS

# --- Configuration ---
HOST_IP = '0.0.0.0' 
PORT = 5000 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'server_storage', 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'server_storage', 'processed')
DB_FILE = os.path.join(BASE_DIR, 'server_storage', 'history.json')

app = Flask(__name__)
CORS(app) 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True) 

# --- Route สำหรับหน้าเว็บ ---
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# --- History Management ---
def load_history():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_history(data):
    current = load_history()
    current = [item for item in current if item['id'] != data['id']]
    current.insert(0, data)
    save_full_history(current)

# ฟังก์ชันบันทึก History แบบทับทั้งหมด (ใช้ตอนลบหรือเปลี่ยนชื่อ)
def save_full_history(history_list):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_list, f, ensure_ascii=False, indent=4)
        f.flush()
        os.fsync(f.fileno())

def delete_from_history(file_id):
    current = load_history()
    new_history = [item for item in current if str(item['id']) != str(file_id)]
    save_full_history(new_history)
    return new_history

# --- Helper: Secure Delete ---
def secure_delete(filepath):
    if not os.path.exists(filepath): return True
    for i in range(5):
        try:
            os.remove(filepath)
            return True
        except PermissionError:
            time.sleep(0.5)
        except Exception:
            return False
    try:
        trash_path = filepath + f".deleted_{uuid.uuid4().hex}"
        os.rename(filepath, trash_path)
        try: os.remove(trash_path)
        except: pass
        return True
    except: return False

# --- Core Logic ---
def check_has_audio(filepath):
    try:
        command = ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', filepath]
        output = subprocess.check_output(command).decode().strip()
        return len(output) > 0
    except: return False

def process_video_task(temp_filepath, original_filename, options, file_id):
    output_filename = f"{os.path.splitext(original_filename)[0]}_{file_id}.wav"
    output_path = os.path.join(PROCESSED_FOLDER, output_filename)
    
    print(f"[{file_id}] Start conversion: {original_filename}")
    
    if not check_has_audio(temp_filepath):
        try: os.remove(temp_filepath)
        except: pass
        return

    channels = '2'
    if options.get('channels') == '4.0': channels = '4'
    elif options.get('channels') == '7.0': channels = '7'
    elif options.get('channels') == '7.1': channels = '8'

    bitrate = options.get('bitrate', '320') + 'k'
    
    bit_depth = options.get('bit_depth', '16')
    codec = 'pcm_s16le'
    if bit_depth == '8': codec = 'pcm_u8'
    elif bit_depth == '24': codec = 'pcm_s24le'
    elif bit_depth == '32': codec = 'pcm_s32le'
    
    cmd = [
        'ffmpeg', '-y', '-i', temp_filepath, '-vn',
        '-acodec', codec, '-ar', '48000', '-ac', channels, '-b:a', bitrate,
        output_path
    ]

    try:
        subprocess.run(cmd, check=True)
        file_stats = os.stat(output_path)
        history_entry = {
            'id': file_id,
            'original_name': original_filename, # ชื่อสำหรับแสดงผล (Display Name)
            'filename': output_filename,        # ชื่อไฟล์จริง (Physical File)
            'size': file_stats.st_size,
            'date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'options': options
        }
        save_history(history_entry)
    except Exception as e:
        print(f"[{file_id}] Error: {e}")
    finally:
        if os.path.exists(temp_filepath): os.remove(temp_filepath)

def background_assembly_task(file_id, total_chunks, filename, options):
    temp_dir = os.path.join(UPLOAD_FOLDER, file_id)
    final_video_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
    try:
        with open(final_video_path, 'wb') as outfile:
            for i in range(total_chunks):
                chunk_path = os.path.join(temp_dir, f"chunk_{i}")
                if os.path.exists(chunk_path):
                    with open(chunk_path, 'rb') as infile: shutil.copyfileobj(infile, outfile)
                    try: os.remove(chunk_path)
                    except: pass
        try: os.rmdir(temp_dir)
        except: pass
        process_video_task(final_video_path, filename, options, file_id)
    except Exception as e: print(f"Assembly Error: {e}")

# --- APIs ---

# API ใหม่: เปลี่ยนชื่อไฟล์ (Rename)
@app.route('/rename/<file_id>', methods=['POST'])
def rename_file(file_id):
    try:
        # Strip ID เพื่อความชัวร์
        file_id = str(file_id).strip()
        
        data = request.json
        new_name_stem = data.get('new_name', '').strip()
        
        print(f"[{file_id}] Request to rename to: {new_name_stem}")

        # 1. ตรวจสอบชื่อว่าง
        if not new_name_stem:
            return jsonify({'status': 'error', 'message': 'กรุณาระบุชื่อไฟล์'}), 400

        # 2. ล้างชื่อไฟล์ (Sanitize) ป้องกันอักขระพิเศษที่ Windows ห้ามใช้
        new_name_stem = re.sub(r'[<>:"/\\|?*]', '', new_name_stem)

        history = load_history()
        target_entry = next((item for item in history if str(item['id']) == file_id), None)

        if not target_entry:
            print(f"[{file_id}] Rename failed: File not found in history")
            return jsonify({'status': 'error', 'message': 'ไม่พบไฟล์ในประวัติ'}), 404

        old_filename = target_entry['filename']
        ext = os.path.splitext(old_filename)[1] # เก็บขั้วไฟล์เดิมไว้ (.wav)
        new_filename = f"{new_name_stem}{ext}"

        # 3. ตรวจสอบชื่อซ้ำใน History
        if any(item['filename'] == new_filename for item in history if str(item['id']) != file_id):
             return jsonify({'status': 'error', 'message': 'ชื่อไฟล์นี้มีอยู่แล้วในระบบ'}), 409
        
        # 4. ตรวจสอบชื่อซ้ำใน Disk
        old_path = os.path.join(PROCESSED_FOLDER, old_filename)
        new_path = os.path.join(PROCESSED_FOLDER, new_filename)

        if os.path.exists(new_path):
             return jsonify({'status': 'error', 'message': 'ชื่อไฟล์นี้มีอยู่แล้วบน Server'}), 409

        if not os.path.exists(old_path):
             print(f"[{file_id}] Rename failed: Original file missing on disk")
             return jsonify({'status': 'error', 'message': 'ไม่พบไฟล์ต้นฉบับบน Server'}), 404

        # 5. ทำการเปลี่ยนชื่อ (Rename)
        try:
            os.rename(old_path, new_path)
        except OSError as e:
            print(f"[{file_id}] Rename OS Error: {e}")
            return jsonify({'status': 'error', 'message': f'เปลี่ยนชื่อไม่สำเร็จ (File Locked): {e}'}), 500

        # 6. อัปเดตข้อมูลใน History
        target_entry['filename'] = new_filename      # อัปเดตชื่อไฟล์จริง
        target_entry['original_name'] = new_name_stem # อัปเดตชื่อแสดงผล
        
        save_full_history(history)
        print(f"[{file_id}] Renamed successfully to {new_filename}")
        
        return jsonify({'status': 'ok', 'new_name': new_filename})

    except Exception as e:
         print(f"Rename API Exception: {e}")
         return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/check_chunks/<file_id>', methods=['GET'])
def check_chunks(file_id):
    temp_dir = os.path.join(UPLOAD_FOLDER, file_id)
    if not os.path.exists(temp_dir): return jsonify({'chunks': []})
    try:
        files = os.listdir(temp_dir)
        chunks = [int(f.split('_')[1]) for f in files if f.startswith('chunk_')]
        return jsonify({'chunks': chunks})
    except: return jsonify({'chunks': []})

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    try:
        file = request.files['file']
        file_id = request.form['file_id']
        chunk_index = int(request.form['chunk_index'])
        temp_dir = os.path.join(UPLOAD_FOLDER, file_id)
        os.makedirs(temp_dir, exist_ok=True)
        file.save(os.path.join(temp_dir, f"chunk_{chunk_index}"))
        return jsonify({'status': 'ok', 'chunk': chunk_index})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/assemble', methods=['POST'])
def assemble_file():
    try:
        data = request.json
        thread = threading.Thread(target=background_assembly_task, args=(data['file_id'], data['total_chunks'], data['filename'], data['options']))
        thread.start()
        return jsonify({'status': 'processing'})
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/delete/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    try:
        file_id = file_id.strip()
        history = load_history()
        target = next((item for item in history if str(item['id']) == str(file_id)), None)
        if target:
            wav_path = os.path.join(PROCESSED_FOLDER, target['filename'])
            secure_delete(wav_path)
            delete_from_history(file_id)
            return jsonify({'status': 'ok'})
        else: return jsonify({'status': 'error'}), 404
    except Exception as e: return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history(): return jsonify(load_history())

@app.route('/stream/<filename>')
def stream_audio(filename):
    path = os.path.join(PROCESSED_FOLDER, filename)
    if not os.path.exists(path): return "File not found", 404
    range_header = request.headers.get('Range', None)
    if not range_header: return send_from_directory(PROCESSED_FOLDER, filename)
    size = os.path.getsize(path)
    byte1 = int(range_header.replace('bytes=', '').split('-')[0])
    length = size - byte1
    with open(path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)
    rv = Response(data, 206, mimetype="audio/wav", direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{size-1}/{size}')
    return rv

if __name__ == '__main__':
    print(f"--- SERVER STARTED on http://{HOST_IP}:{PORT} ---")
    app.run(host=HOST_IP, port=PORT, threaded=True)