from flask import Flask, request, render_template_string, render_template, send_file,jsonify,abort
import qrcode
import io
import json
import os
import csv
from datetime import date, datetime
import socket
from flask_basicauth import BasicAuth


app = Flask(__name__)
app.config['BASIC_AUTH_USERNAME'] = 'admin'  # اسم المستخدم
app.config['BASIC_AUTH_PASSWORD'] = 'admin'  # كلمة المرور
basic_auth = BasicAuth(app)
# إعداد اسم المجلد لتخزين البيانات
results_folder = 'results'

# إنشاء المجلد إذا لم يكن موجوداً
if not os.path.exists(results_folder):
    os.makedirs(results_folder)

# إعداد ملفات JSON وCSV لتخزين بيانات الحضور
today = date.today()
attendance_file = os.path.join(results_folder, f"{today}.json")
csv_file = os.path.join(results_folder, f"{today}.csv")

def read_attendance():
    if os.path.exists(attendance_file):
        with open(attendance_file, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return {}
    else:
        return {}

def write_attendance(data):
    with open(attendance_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def json_to_csv(json_filename, csv_filename):
    try:
        # قراءة بيانات JSON من الملف
        with open(json_filename, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)

        # فتح ملف CSV للكتابة باستخدام utf-8-sig
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csv_file:
            # تحديد أسماء الأعمدة
            fieldnames = ['IP', 'name', 'student_id', 'subject', 'timestamp', 'department']  # إضافة حقل المادة
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            
            # كتابة رؤوس الأعمدة
            writer.writeheader()
            
            # كتابة البيانات
            for ip, details in data.items():
                if isinstance(details, dict):  # تأكد من أن details هو قاموس
                    row = {'IP': ip, **details}
                    writer.writerow(row)
                else:
                    print(f"Expected a dictionary but got {type(details)} for IP {ip}")

        print(f'Data has been written to {csv_filename}')
    
    except FileNotFoundError:
        print(f"The file {json_filename} was not found.")
    except json.JSONDecodeError:
        print("Error decoding JSON. Please check the format of your JSON file.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

@app.route('/')
def index():
    # إعداد قيمة data لعرضها في HTML
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    s.connect(('8.8.8.8', 80))
    internal_ip = s.getsockname()[0]
    data = f"http://{internal_ip}:5000"
    
    return render_template('index.html', data=data)

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    student_id = request.form.get('student_id')
    subject = request.form.get('subject')
    department = request.form.get('department')
    ip = request.remote_addr
    allow_multiple = 'allow_multiple' in request.form
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    device_fingerprint = request.form.get('device_fingerprint')

    # قراءة سجلات الحضور
    attendance = read_attendance()
 
    combined_key = f"{ip}|{device_fingerprint}"
    if not allow_multiple and combined_key in attendance:
        print('ip,device_fingerprint')
        return render_template("error.html")
    elif not allow_multiple and any(key.startswith(f"{ip}|") for key in attendance.keys()):
        print('ip')
        return render_template("error.html")

    elif not allow_multiple and any(key.endswith(f"|{device_fingerprint}") for key in attendance.keys()):
        print('device_fingerprint')
        return render_template("error.html")

   

    # إضافة سجل جديد
    attendance[combined_key] = {"name": name, "student_id": student_id, "subject": subject, "department": department, "timestamp": current_time}

    # كتابة البيانات المحدثة إلى الملف
    write_attendance(attendance)
    
    # تحويل JSON إلى CSV
    json_to_csv(attendance_file, csv_file)

    # إعداد قيمة data لعرضها في HTML
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    s.connect(('8.8.8.8', 80))
    internal_ip = s.getsockname()[0]
    data = f"http://{internal_ip}:5000"
    
    return render_template('success.html', data=data)

@app.route('/qr')
def qr():
    # توليد رمز الاستجابة السريعة (QR code)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    s.connect(('8.8.8.8', 80))
    internal_ip = s.getsockname()[0]
    url = f"http://{internal_ip}:5000"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    # حفظ الصورة في الذاكرة وإرسالها للمتصفح
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    
    return send_file(buf, mimetype='image/png')

@app.route('/data')
@basic_auth.required
def get_data():
    
    if os.path.exists(attendance_file):
        with open(attendance_file, 'r', encoding='utf-8') as file:
            try:
                data = json.load(file)
                return jsonify(data)
            except json.JSONDecodeError:
                return jsonify({"error": "Failed to decode JSON"}), 500
    else:
        return jsonify({"error": "File not found"}), 404

@app.route('/show')
@basic_auth.required
def show():
    return render_template('show.html')
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
