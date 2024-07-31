from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for flash messages and session management

DATABASE = os.path.join(os.path.dirname(__file__), 'instance', 'database.db')
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'admin_credentials.txt')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        with get_db() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

def read_admin_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        return None, None
    
    with open(CREDENTIALS_FILE, 'r') as file:
        lines = file.readlines()
        if len(lines) >= 2:
            username = lines[0].strip()
            password = lines[1].strip()
            return username, password
    return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not os.path.exists(DATABASE):
            flash("Database does not exist. Please contact the administrator.", "error")
            return render_template('login.html')

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user:
            if user['password'] == password:
                flash("Login successful!", "success")
                session.pop('admin_logged_in', None)  # Ensure admin session is cleared
                return redirect(url_for('index'))
            else:
                flash("Invalid credentials.", "error")
        else:
            flash("User not found or incorrect credentials.", "error")
        
        return render_template('login.html')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        
        if not (name and username and password and confirm_password):
            flash("All fields are required.", "error")
            return redirect(url_for('signup'))
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for('signup'))
        
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (name, username, password) VALUES (?, ?, ?)',
                         (name, username, password))
            conn.commit()
            flash("Sign up successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "error")
            return redirect(url_for('signup'))
        finally:
            conn.close()
    
    return render_template('signup.html')

@app.route('/view_database', methods=['GET'])
def view_database():
    if not session.get('admin_logged_in'):
        flash("Please log in as an admin.", "error")
        return redirect(url_for('admin_login'))

    query = request.args.get('query', '')

    # Prepare SQL query with placeholders
    sql_query = 'SELECT * FROM users WHERE name LIKE ? OR username LIKE ? OR id LIKE ?'
    parameters = (f'%{query}%', f'%{query}%', f'%{query}%')

    conn = get_db()
    users = conn.execute(sql_query, parameters).fetchall()
    conn.close()

    return render_template('view_database.html', users=users)

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if not session.get('admin_logged_in'):
        flash("Please log in as an admin.", "error")
        return redirect(url_for('admin_login'))

    user_id = request.form.get('user_id')
    
    if user_id:
        conn = get_db()
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        flash("User deleted successfully.", "success")
    else:
        flash("No user selected for deletion.", "error")
    
    return redirect(url_for('view_database'))

@app.route('/add_user', methods=['POST'])
def add_user():
    if not session.get('admin_logged_in'):
        flash("Please log in as an admin.", "error")
        return redirect(url_for('admin_login'))

    name = request.form['name']
    username = request.form['username']
    password = request.form['password']
    
    if not (name and username and password):
        flash("All fields are required.", "error")
        return redirect(url_for('view_database'))
    
    conn = get_db()
    try:
        conn.execute('INSERT INTO users (name, username, password) VALUES (?, ?, ?)',
                     (name, username, password))
        conn.commit()
        flash("User added successfully.", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists.", "error")
    finally:
        conn.close()
    
    return redirect(url_for('view_database'))

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin_username, admin_password = read_admin_credentials()

        if username == admin_username and password == admin_password:
            session['admin_logged_in'] = True
            return redirect(url_for('view_database'))
        else:
            flash("Invalid admin credentials.", "error")
            return redirect(url_for('admin_login'))
    
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)  # Clear the session
    flash("You have been logged out.", "success")
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
