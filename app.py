from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date, datetime

app = Flask(__name__)
DB = 'team_tracker.db'


@app.template_filter('fmt_date')
def fmt_date(s):
    if not s:
        return ''
    return datetime.strptime(s, '%Y-%m-%d').strftime('%b %-d')


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS teammates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teammate_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                pct_complete INTEGER DEFAULT 0,
                completed_date TEXT,
                FOREIGN KEY (teammate_id) REFERENCES teammates(id)
            );
            CREATE TABLE IF NOT EXISTS progress_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                pct_complete INTEGER NOT NULL,
                updated_date TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        ''')
        if conn.execute('SELECT COUNT(*) FROM teammates').fetchone()[0] == 0:
            for name in ['Adam Ouriel', 'Seori Sachs', 'Daniel Reyes', 'Ronny Coste']:
                conn.execute('INSERT INTO teammates (name) VALUES (?)', (name,))


@app.route('/')
def index():
    db = get_db()
    teammates = db.execute('SELECT * FROM teammates ORDER BY name').fetchall()
    overview = []
    for t in teammates:
        projects = db.execute(
            'SELECT * FROM projects WHERE teammate_id = ? ORDER BY start_date DESC', (t['id'],)
        ).fetchall()
        active = [p for p in projects if not p['completed_date']]
        done = [p for p in projects if p['completed_date']]
        avg_pct = round(sum(p['pct_complete'] for p in active) / len(active)) if active else 0
        overview.append({
            'teammate': t,
            'active': active,
            'done': done,
            'avg_pct': avg_pct,
        })
    total_active = sum(len(item['active']) for item in overview)
    return render_template('index.html', overview=overview, total_active=total_active)


@app.route('/teammate/<int:tid>')
def teammate(tid):
    db = get_db()
    t = db.execute('SELECT * FROM teammates WHERE id = ?', (tid,)).fetchone()
    if not t:
        return redirect(url_for('index'))
    projects = db.execute(
        'SELECT * FROM projects WHERE teammate_id = ? ORDER BY completed_date ASC, start_date DESC',
        (tid,)
    ).fetchall()
    history = {}
    for p in projects:
        history[p['id']] = db.execute(
            'SELECT pct_complete, updated_date FROM progress_history WHERE project_id = ? ORDER BY updated_date DESC',
            (p['id'],)
        ).fetchall()
    return render_template('teammate.html', teammate=t, projects=projects, today=date.today().isoformat(), history=history)


@app.route('/teammate/<int:tid>/add', methods=['POST'])
def add_project(tid):
    name = request.form['name'].strip()
    start_date = request.form['start_date']
    if name and start_date:
        with get_db() as db:
            db.execute(
                'INSERT INTO projects (teammate_id, name, start_date, pct_complete) VALUES (?, ?, ?, 0)',
                (tid, name, start_date)
            )
    return redirect(url_for('teammate', tid=tid))


@app.route('/project/<int:pid>/update', methods=['POST'])
def update_project(pid):
    pct = max(0, min(100, int(request.form.get('pct_complete', 0))))
    mark_complete = request.form.get('mark_complete')
    completed_date = date.today().isoformat() if mark_complete else None
    today = date.today().isoformat()
    with get_db() as db:
        project = db.execute('SELECT teammate_id FROM projects WHERE id = ?', (pid,)).fetchone()
        db.execute(
            'UPDATE projects SET pct_complete = ?, completed_date = ? WHERE id = ?',
            (pct, completed_date, pid)
        )
        db.execute(
            'INSERT INTO progress_history (project_id, pct_complete, updated_date) VALUES (?, ?, ?)',
            (pid, pct, today)
        )
    return redirect(url_for('teammate', tid=project['teammate_id']))


@app.route('/project/<int:pid>/delete', methods=['POST'])
def delete_project(pid):
    with get_db() as db:
        project = db.execute('SELECT teammate_id FROM projects WHERE id = ?', (pid,)).fetchone()
        db.execute('DELETE FROM projects WHERE id = ?', (pid,))
    return redirect(url_for('teammate', tid=project['teammate_id']))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
