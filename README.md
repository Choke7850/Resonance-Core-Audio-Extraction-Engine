🎵 Resonance Core: Audio Extractor

High-Performance Web-based Audio Extraction Platform

ระบบแปลงไฟล์วิดีโอเป็นเสียงคุณภาพสูง (WAV 16/24/32-bit) ผ่านหน้าเว็บ รองรับไฟล์ขนาดใหญ่ (Large File Support) พร้อมระบบ Resume Upload และจัดการไฟล์แบบ Real-time

✨ Features (ฟีเจอร์เด่น)

🚀 Chunked Upload System: รองรับการอัปโหลดไฟล์ขนาดใหญ่ (GB/TB) โดยไม่กิน Ram

Resumable Upload: เน็ตหลุดหรือปิดหน้าเว็บ กลับมาอัปโหลดต่อจากเดิมได้ทันที (Hash-based Check)

🎛️ Audio Customization:

Bitrate: สูงสุด 2048 kbps

Bit Depth: รองรับ 8, 16, 24, 32-bit (PCM)

Channels: รองรับ Mono, Stereo, 4.0, 5.1, 7.1 Surround

UI/UX: Glassmorphism Design พร้อม Animation และ Custom Dropdown

Management: เปลี่ยนชื่อไฟล์ (Rename), ลบไฟล์ (Secure Delete), และฟังเพลงผ่านหน้าเว็บ

🛠️ Installation (การติดตั้ง)

Clone Repository

git clone [https://github.com/yourusername/resonance-core.git](https://github.com/yourusername/resonance-core.git)
cd resonance-core


Install Dependencies

pip install -r requirements.txt


Install FFmpeg

ต้องติดตั้ง FFmpeg ลงในเครื่องและ Set Path ให้เรียบร้อย

Run Server

python server.py


Server จะรันที่ http://localhost:5000

👨‍💻 Credits

Lead Developer & Engineering: Chok (Electronic Specialist)

Co-Developer / AI Assistant: Gemini (Google)

Developed with ❤️ using Python Flask & React