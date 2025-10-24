# รายรับ-รายจ่าย (Flask + SQLite)

แอปตัวอย่างสำหรับบันทึกรายรับ-รายจ่าย พร้อมสรุปยอดรายวัน/เดือน/ปี, CRUD, ค้นหา, pagination, สมัครสมาชิก/ล็อกอิน, admin จัดการสมาชิก, นำเข้า/ส่งออก CSV และแสดง pie chart ตามเดือน/ปี

การติดตั้ง (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# รัน
python app.py
# เปิดเบราว์เซอร์ไปที่ http://127.0.0.1:5000
```

บัญชีเริ่มต้น:
- username: admin
- password: admin

หมายเหตุ:
- ไฟล์ฐานข้อมูล `data.db` จะถูกสร้างอัตโนมัติในโฟลเดอร์โปรเจค
- เมนู Chart ใช้ Chart.js และสามารถเลือก month/year ได้
- ค่า lookup รายรับ/รายจ่ายถูกตั้งไว้ใน `app.py` หากต้องการเพิ่มรายการถาวร ให้แก้ตัวแปร `INCOME_LOOKUP` และ `EXPENSE_LOOKUP`

ถ้าต้องการ ผมสามารถ:
- เพิ่ม test เล็กๆ ให้ตรวจสอบ CRUD
- แยก models และ route เป็นไฟล์ย่อยเพื่อความเป็นระเบียบ
- เพิ่มการยืนยันอีเมลหรือ reset password
run program
cd d:\AI\new_project
.\.venv\Scripts\Activate.ps1
python run_server.py