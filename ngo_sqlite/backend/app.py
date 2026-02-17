from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__,
            template_folder='../frontend/templates',
            static_folder='../frontend/static')
app.secret_key = 'ngo_secret_key_2024'

# SQLite database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ngo_projects.db')

# Upload config
UPLOAD_FOLDER = os.path.join(BASE_DIR, '../frontend/static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Ongoing','Completed','Upcoming')),
            start_date TEXT,
            end_date TEXT,
            location TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            image_url TEXT NOT NULL,
            uploaded_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')

    # Insert sample data only if empty
    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO projects (title, description, status, start_date, location)
            VALUES (?, ?, ?, ?, ?)
        ''', [
            ('Education for All',
             'Providing quality education to underprivileged children in rural areas. This project focuses on improving literacy rates and creating opportunities for a better future.',
             'Ongoing', '2024-01-15', 'Rural Maharashtra'),
            ('Clean Water Initiative',
             'Installing water purification systems in villages lacking access to clean drinking water. Our goal is to reduce waterborne diseases and improve health standards.',
             'Completed', '2023-06-01', 'Pune District'),
            ('Healthcare Outreach',
             'Mobile medical camps providing free healthcare services to remote communities. Regular health checkups and medicine distribution program.',
             'Upcoming', '2024-03-01', 'Multiple Villages'),
        ])

    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========== PUBLIC ROUTES ==========

@app.route('/')
def index():
    conn = get_db()
    status_filter = request.args.get('status', 'all')

    if status_filter == 'all':
        projects = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    else:
        projects = conn.execute(
            "SELECT * FROM projects WHERE status=? ORDER BY created_at DESC",
            (status_filter,)
        ).fetchall()

    projects = [dict(p) for p in projects]
    for project in projects:
        images = conn.execute(
            "SELECT * FROM project_images WHERE project_id=?", (project['id'],)
        ).fetchall()
        project['images'] = [dict(i) for i in images]

    ongoing   = conn.execute("SELECT COUNT(*) FROM projects WHERE status='Ongoing'").fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM projects WHERE status='Completed'").fetchone()[0]
    upcoming  = conn.execute("SELECT COUNT(*) FROM projects WHERE status='Upcoming'").fetchone()[0]
    total     = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()

    stats = {'people_helped': '500+', 'volunteers': '300+', 'funds_raised': '$50,000+'}
    return render_template('index.html',
                           projects=projects, stats=stats,
                           current_filter=status_filter,
                           completed_count=completed,
                           ongoing_count=ongoing,
                           upcoming_count=upcoming,
                           total_count=total)

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    conn = get_db()
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return "Project not found", 404
    project = dict(project)
    images = conn.execute(
        "SELECT * FROM project_images WHERE project_id=?", (project_id,)
    ).fetchall()
    project['images'] = [dict(i) for i in images]
    conn.close()
    return render_template('project_detail.html', project=project)

# ========== ADMIN ROUTES ==========

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials!', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out!', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    conn = get_db()
    projects = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    projects = [dict(p) for p in projects]
    for project in projects:
        images = conn.execute(
            "SELECT * FROM project_images WHERE project_id=?", (project['id'],)
        ).fetchall()
        project['images'] = [dict(i) for i in images]
    conn.close()
    return render_template('admin_dashboard.html', projects=projects)

@app.route('/admin/project/add', methods=['POST'])
def admin_add_project():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    try:
        title       = request.form.get('title')
        description = request.form.get('description')
        status      = request.form.get('status')
        start_date  = request.form.get('start_date') or None
        end_date    = request.form.get('end_date') or None
        location    = request.form.get('location')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (title, description, status, start_date, end_date, location)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, description, status, start_date, end_date, location))
        project_id = cursor.lastrowid

        if 'images' in request.files:
            for file in request.files.getlist('images'):
                if file and allowed_file(file.filename):
                    filename  = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename  = f"{timestamp}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    cursor.execute(
                        "INSERT INTO project_images (project_id, image_url) VALUES (?, ?)",
                        (project_id, f"uploads/{filename}")
                    )
        conn.commit()
        conn.close()
        flash('Project added successfully!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/project/edit/<int:project_id>', methods=['POST'])
def admin_edit_project(project_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    try:
        title       = request.form.get('title')
        description = request.form.get('description')
        status      = request.form.get('status')
        start_date  = request.form.get('start_date') or None
        end_date    = request.form.get('end_date') or None
        location    = request.form.get('location')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE projects SET title=?, description=?, status=?,
            start_date=?, end_date=?, location=?, updated_at=datetime('now')
            WHERE id=?
        ''', (title, description, status, start_date, end_date, location, project_id))

        if 'images' in request.files:
            for file in request.files.getlist('images'):
                if file and file.filename and allowed_file(file.filename):
                    filename  = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename  = f"{timestamp}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    cursor.execute(
                        "INSERT INTO project_images (project_id, image_url) VALUES (?, ?)",
                        (project_id, f"uploads/{filename}")
                    )
        conn.commit()
        conn.close()
        flash('Project updated!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/project/delete/<int:project_id>', methods=['POST'])
def admin_delete_project(project_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    try:
        conn = get_db()
        conn.execute("DELETE FROM project_images WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        conn.commit()
        conn.close()
        flash('Project deleted!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
