import os
from datetime import datetime, date
from io import StringIO
import io
import csv
import pytz

# Set Thailand timezone
TH_TZ = pytz.timezone('Asia/Bangkok')

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   send_file, jsonify)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'dev-secret')

# Use PostgreSQL URL from Railway in production, fallback to SQLite for local development
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{DB_PATH}')
if DATABASE_URL.startswith('postgres://'):
    # Replace postgres:// with postgresql:// for SQLAlchemy
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable production mode if not in debug
if not os.environ.get('FLASK_DEBUG', False):
    app.config['ENV'] = 'production'
    app.config['DEBUG'] = False

# Add to_thai_time to template context
@app.context_processor
def utility_processor():
    return {'to_thai_time': to_thai_time}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Predefined lookup lists
INCOME_LOOKUP = [
    'ถ่ายเอกสาร A4 ขาวดำ', 'ถ่ายเอกสาร A4 สี', 'print A4 ขาวดำ', 'print A4 สี',
    'เคลือบบัตร ขนาดการ์ดทั่วไป', 'เคลือบบัตรขนาด A4', 'ถ่ายเอกสาร A3 สี',
    'ถ่ายเอกสาร A3 ขาวดำ', 'print A3 ขาวดำ', 'print A3', 'อื่นๆ'
]

EXPENSE_LOOKUP = ['ค่าหมึก', 'ค่ากระดาษ', 'ค่าน้ำ', 'ค่าไฟ', 'อื่นๆ']

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_income = db.Column(db.Boolean, nullable=False)  # True=income, False=expense
    category = db.Column(db.String(120), nullable=True)
    custom_name = db.Column(db.String(200), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(TH_TZ))

    user = db.relationship('User', backref='entries')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Ensure DB
@app.before_first_request
def create_tables():
    db.create_all()
    # create default admin if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        a = User(username='admin', is_admin=True)
        a.set_password('admin')
        db.session.add(a)
        db.session.commit()

# Utility functions
def to_thai_time(dt):
    """Convert UTC datetime to Thailand timezone"""
    if dt.tzinfo is None:  # If naive datetime, assume it's UTC
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(TH_TZ)

def now_thai():
    """Get current time in Thailand timezone"""
    return datetime.now(TH_TZ)

def summarize(user_id=None):
    # Returns daily, monthly, yearly totals (income - expense)
    q = Entry.query
    if user_id:
        q = q.filter_by(user_id=user_id)
    entries = q.all()
    today = now_thai().date()
    daily = sum(e.amount if e.is_income else -e.amount for e in entries if to_thai_time(e.created_at).date() == today)
    monthly = sum(e.amount if e.is_income else -e.amount for e in entries if to_thai_time(e.created_at).year == today.year and to_thai_time(e.created_at).month == today.month)
    yearly = sum(e.amount if e.is_income else -e.amount for e in entries if to_thai_time(e.created_at).year == today.year)
    return {'daily': daily, 'monthly': monthly, 'yearly': yearly}

def get_monthly_stats(month=None, year=None):
    # Get income, expense and balance for a specific month
    if month is None:
        month = datetime.utcnow().month
    if year is None:
        year = datetime.utcnow().year
    
    entries = Entry.query.filter(
        db.extract('year', Entry.created_at) == year,
        db.extract('month', Entry.created_at) == month
    ).all()
    
    income = sum(e.amount for e in entries if e.is_income)
    expense = sum(e.amount for e in entries if not e.is_income)
    balance = income - expense
    
    return {'income': income, 'expense': expense, 'balance': balance}

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/ping')
def ping():
    # simple liveness check
    return 'ok', 200

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('ชื่อผู้ใช้นี้มีอยู่แล้ว')
            return redirect(url_for('register'))
        u = User(username=username)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash('สมัครสมาชิกเรียบร้อย กรุณาเข้าสู่ระบบ')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        u = User.query.filter_by(username=username).first()
        if u and u.check_password(password):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    sel_month = request.args.get('month')
    sel_year = request.args.get('year')
    # default to current Thai time
    now = now_thai()
    month = int(sel_month) if sel_month and sel_month.isdigit() else now.month
    year = int(sel_year) if sel_year and sel_year.isdigit() else now.year

    # totals (show across all users)
    sums = summarize()

    # prepare last 10 entries
    page = int(request.args.get('page', 1))
    per_page = 10
    # list all entries (all users) — users can view all but may only edit/delete their own unless admin
    q = Entry.query.order_by(Entry.created_at.desc())
    # search support
    q_text = request.args.get('q')
    if q_text:
        q = q.filter((Entry.category.ilike(f'%{q_text}%')) | (Entry.custom_name.ilike(f'%{q_text}%')) | (Entry.notes.ilike(f'%{q_text}%')))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # Get monthly statistics
    monthly_stats = get_monthly_stats(month=month, year=year)
    
    return render_template('dashboard.html', income_lookup=INCOME_LOOKUP, expense_lookup=EXPENSE_LOOKUP,
                           pagination=pagination, sums=sums, month=month, year=year, q=q_text,
                           monthly_stats=monthly_stats)

@app.route('/add-entry', methods=['POST'])
@login_required
def add_entry():
    kind = request.form.get('kind')  # 'income' or 'expense'
    is_income = True if kind == 'income' else False
    category = request.form.get('category') or None
    custom_name = request.form.get('custom_name') or None
    try:
        amount = float(request.form.get('amount') or 0)
    except ValueError:
        flash('จำนวนเงินไม่ถูกต้อง')
        return redirect(url_for('dashboard'))
    notes = request.form.get('notes')
    if not category and not custom_name:
        flash('กรุณาเลือกหรือพิมพ์ชื่อรายการ')
        return redirect(url_for('dashboard'))
    # store created_at using Thailand timezone so display matches DB saved value
    e = Entry(user_id=current_user.id, is_income=is_income, category=category, custom_name=custom_name, amount=amount, notes=notes, created_at=now_thai())
    db.session.add(e)
    db.session.commit()
    flash('บันทึกรายการเรียบร้อย')
    return redirect(url_for('dashboard'))

@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit(entry_id):
    e = Entry.query.get_or_404(entry_id)
    if e.user_id != current_user.id and not current_user.is_admin:
        flash('ไม่มีสิทธิ์แก้ไข')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        e.is_income = True if request.form.get('kind') == 'income' else False
        e.category = request.form.get('category') or None
        e.custom_name = request.form.get('custom_name') or None
        try:
            e.amount = float(request.form.get('amount') or 0)
        except ValueError:
            flash('จำนวนเงินไม่ถูกต้อง')
            return redirect(url_for('edit', entry_id=entry_id))
        e.notes = request.form.get('notes')
        
        # Handle date and time
        try:
            entry_date = request.form.get('entry_date')
            entry_time = request.form.get('entry_time', '00:00')
            datetime_str = f"{entry_date} {entry_time}"
            # Parse input and store as Thailand timezone-aware datetime
            parsed = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            if parsed.tzinfo is None:
                created_at = TH_TZ.localize(parsed)
            else:
                created_at = parsed.astimezone(TH_TZ)
            e.created_at = created_at
        except (ValueError, TypeError):
            flash('รูปแบบวันที่หรือเวลาไม่ถูกต้อง')
            return redirect(url_for('edit', entry_id=entry_id))
            
        db.session.commit()
        flash('แก้ไขเรียบร้อย')
        return redirect(url_for('dashboard'))
    return render_template('edit.html', entry=e, income_lookup=INCOME_LOOKUP, expense_lookup=EXPENSE_LOOKUP)

@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete(entry_id):
    e = Entry.query.get_or_404(entry_id)
    if e.user_id != current_user.id and not current_user.is_admin:
        flash('ไม่มีสิทธิ์ลบ')
        return redirect(url_for('dashboard'))
    db.session.delete(e)
    db.session.commit()
    flash('ลบเรียบร้อย')
    return redirect(url_for('dashboard'))

@app.route('/delete-all', methods=['POST'])
@login_required
def delete_all():
    # delete all entries for current user
    Entry.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('ลบรายการทั้งหมดเรียบร้อย')
    return redirect(url_for('dashboard'))

@app.route('/export-csv')
@login_required
def export_csv():
    try:
        # Build CSV in text, then encode to bytes to avoid TextIOWrapper/BytesIO issues
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['id', 'is_income', 'category', 'custom_name', 'amount', 'notes', 'created_at'])
        # export all entries (across users)
        entries = Entry.query.order_by(Entry.created_at.asc()).all()
        for e in entries:
            cw.writerow([e.id, e.is_income, e.category or '', e.custom_name or '', e.amount, e.notes or '', e.created_at.isoformat()])
        text = si.getvalue()
        # Encode with BOM for better Excel compatibility (optional)
        data = text.encode('utf-8-sig')
        bio = io.BytesIO(data)
        bio.seek(0)
        return send_file(bio, mimetype='text/csv; charset=utf-8', as_attachment=True, download_name='entries.csv')
    except Exception:
        import traceback
        traceback.print_exc()
        flash('เกิดข้อผิดพลาดขณะส่งออก CSV')
        return redirect(url_for('dashboard'))


@app.route('/export-csv-debug')
@login_required
def export_csv_debug():
    """Return CSV as plain text in the browser (no attachment) to help debug encoding/IO issues."""
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'is_income', 'category', 'custom_name', 'amount', 'notes', 'created_at'])
    # debug: show all entries
    entries = Entry.query.order_by(Entry.created_at.asc()).all()
    for e in entries:
        cw.writerow([e.id, e.is_income, e.category or '', e.custom_name or '', e.amount, e.notes or '', e.created_at.isoformat()])
    text = si.getvalue()
    return text, 200, {'Content-Type': 'text/csv; charset=utf-8'}

@app.route('/import-csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f:
            flash('โปรดเลือกไฟล์')
            return redirect(url_for('dashboard'))
        data = f.stream.read().decode('utf-8')
        reader = csv.DictReader(StringIO(data))
        count = 0
        for row in reader:
            try:
                is_income = row.get('is_income','').lower() in ('1','true','yes')
                cat = row.get('category') or None
                custom = row.get('custom_name') or None
                amount = float(row.get('amount') or 0)
                # parse created_at from CSV; if naive, localize to Thailand tz; if missing/invalid, use now_thai()
                raw_created = row.get('created_at')
                if raw_created:
                    try:
                        parsed = datetime.fromisoformat(raw_created)
                        if parsed.tzinfo is None:
                            created_at = TH_TZ.localize(parsed)
                        else:
                            created_at = parsed.astimezone(TH_TZ)
                    except Exception:
                        created_at = now_thai()
                else:
                    created_at = now_thai()

                e = Entry(user_id=current_user.id, is_income=is_income, category=cat, custom_name=custom, amount=amount, notes=row.get('notes'), created_at=created_at)
                db.session.add(e)
                count += 1
            except Exception as ex:
                print('skip row', ex)
                continue
        db.session.commit()
        flash(f'นำเข้า {count} รายการ')
        return redirect(url_for('dashboard'))
    return redirect(url_for('dashboard'))

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('ต้องเป็นผู้ดูแลระบบ')
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.username).all()
    return render_template('admin.html', users=users)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash('ต้องเป็นผู้ดูแลระบบ')
        return redirect(url_for('dashboard'))
    u = User.query.get_or_404(user_id)
    if u.username == 'admin':
        flash('ไม่สามารถลบ admin หลักได้')
        return redirect(url_for('admin'))
    Entry.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()
    flash('ลบสมาชิกเรียบร้อย')
    return redirect(url_for('admin'))


@app.route('/admin/create-user', methods=['POST'])
@login_required
def admin_create_user():
    if not current_user.is_admin:
        flash('ต้องเป็นผู้ดูแลระบบ')
        return redirect(url_for('dashboard'))
    username = request.form.get('username','').strip()
    password = request.form.get('password','')
    is_admin = bool(request.form.get('is_admin'))
    if not username or not password:
        flash('กรุณากรอกชื่อผู้ใช้และรหัสผ่าน')
        return redirect(url_for('admin'))
    if User.query.filter_by(username=username).first():
        flash('ชื่อผู้ใช้นี้มีอยู่แล้ว')
        return redirect(url_for('admin'))
    u = User(username=username, is_admin=is_admin)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash('สร้างสมาชิกเรียบร้อย')
    return redirect(url_for('admin'))


@app.route('/admin/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
def admin_toggle_admin(user_id):
    if not current_user.is_admin:
        flash('ต้องเป็นผู้ดูแลระบบ')
        return redirect(url_for('dashboard'))
    u = User.query.get_or_404(user_id)
    if u.username == 'admin':
        flash('ไม่สามารถเปลี่ยนสิทธิ์ admin หลักได้')
        return redirect(url_for('admin'))
    u.is_admin = not u.is_admin
    db.session.commit()
    flash('ปรับสิทธิ์เรียบร้อย')
    return redirect(url_for('admin'))


@app.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    if not current_user.is_admin:
        flash('ต้องเป็นผู้ดูแลระบบ')
        return redirect(url_for('dashboard'))
    u = User.query.get_or_404(user_id)
    if u.username == 'admin':
        flash('ไม่สามารถรีเซ็ตรหัสผ่าน admin หลักได้')
        return redirect(url_for('admin'))
    new_pw = request.form.get('new_password','').strip()
    if not new_pw:
        flash('กรุณากรอกรหัสผ่านใหม่')
        return redirect(url_for('admin'))
    u.set_password(new_pw)
    db.session.commit()
    flash('รีเซ็ตรหัสผ่านเรียบร้อย')
    return redirect(url_for('admin'))


@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Allow any logged-in user (including admin) to change their own password by supplying current and new passwords."""
    current_pw = request.form.get('current_password','')
    new_pw = request.form.get('new_password','')
    if not current_pw or not new_pw:
        flash('กรุณากรอกรหัสผ่านปัจจุบันและรหัสผ่านใหม่')
        return redirect(url_for('admin'))
    user = User.query.get(current_user.id)
    if not user.check_password(current_pw):
        flash('รหัสผ่านปัจจุบันไม่ถูกต้อง')
        return redirect(url_for('admin'))
    user.set_password(new_pw)
    db.session.commit()
    flash('เปลี่ยนรหัสผ่านเรียบร้อย')
    return redirect(url_for('admin'))

@app.route('/monthly-stats')
@login_required
def monthly_stats():
    month = int(request.args.get('month') or datetime.utcnow().month)
    year = int(request.args.get('year') or datetime.utcnow().year)
    stats = get_monthly_stats(month, year)
    return jsonify(stats)

@app.route('/chart-data')
@login_required
def chart_data():
    # returns pie chart data for selected month/year and kind (income/expense)
    month = int(request.args.get('month') or datetime.utcnow().month)
    year = int(request.args.get('year') or datetime.utcnow().year)
    kind = request.args.get('kind') or 'expense'
    is_income = True if kind == 'income' else False
    # include entries from all users for chart
    entries = Entry.query.filter_by(is_income=is_income).filter(db.extract('year', Entry.created_at) == year, db.extract('month', Entry.created_at) == month).all()
    sums = {}
    for e in entries:
        key = e.category or e.custom_name or 'อื่นๆ'
        sums[key] = sums.get(key, 0) + e.amount
    labels = list(sums.keys())
    values = [sums[k] for k in labels]
    return jsonify({'labels': labels, 'values': values})

if __name__ == '__main__':
    app.run(debug=True)