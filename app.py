from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
import uuid

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
                session['username'] = username  # Store username in session
                return redirect(url_for('room_options'))
            else:
                flash("Invalid credentials.", "error")
        else:
            flash("User not found or incorrect credentials.", "error")
        
        return render_template('login.html')
    
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')  # Use .get() to avoid KeyError
        password = request.form.get('password')

        admin_username, admin_password = read_admin_credentials()

        if username == admin_username and password == admin_password:
            flash("Admin login successful!", "success")
            session['admin_logged_in'] = True
            return redirect(url_for('view_database'))
        else:
            flash("Invalid admin credentials.", "error")
    
    return render_template('admin_login.html')


@app.route('/view_database', methods=['GET', 'POST'])
def view_database():
    if 'admin_logged_in' not in session:
        flash("You need to log in as an admin first.", "error")
        return redirect(url_for('admin_login'))

    conn = get_db()
    query = request.args.get('query', '')
    if query:
        users = conn.execute('SELECT * FROM users WHERE id LIKE ? OR name LIKE ? OR username LIKE ?', 
                             ('%' + query + '%', '%' + query + '%', '%' + query + '%')).fetchall()
    else:
        users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        if user_id:
            conn = get_db()
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            flash("User deleted successfully.", "success")
            return redirect(url_for('view_database'))

    return render_template('view_database.html', users=users)

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'admin_logged_in' not in session:
        flash("You need to log in as an admin first.", "error")
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
        conn.close()
        flash("User added successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists.", "error")

    return redirect(url_for('view_database'))

@app.route('/room_options')
def room_options():
    if 'username' not in session and 'admin_logged_in' not in session:
        flash("You need to log in first.", "error")
        return redirect(url_for('login'))
    return render_template('room_options.html')

@app.route('/room_input', methods=['GET', 'POST'])
def room_input():
    if request.method == 'POST':
        room_id = request.form['room_id']
        username = request.form['username']
        if not room_id:
            flash("Room ID is required.", "error")
            return render_template('room_input.html')
        
        # Store the room ID and username in session or process them as needed
        session['room_id'] = room_id
        session['room_username'] = username
        
        # Normally, you would validate the room ID here
        return redirect(url_for('room', room_id=room_id))
    
    return render_template('room_input.html')

@app.route('/create_room', methods=['GET', 'POST'])
def create_room():
    if request.method == 'POST':
        room_id = str(uuid.uuid4())  # Generate a unique room ID
        username = request.form['username']
        
        # Store the room ID and username in session or process them as needed
        session['room_id'] = room_id
        session['room_username'] = username
        
        flash(f"Room created successfully! Room ID: {room_id}", "success")
        return redirect(url_for('room', room_id=room_id))
    
    return render_template('create_room.html')

@app.route('/room', methods=['GET'])
def room():
    room_id = request.args.get('room_id', None)
    if not room_id:
        flash("No room ID provided.", "error")
        return redirect(url_for('index'))
    return render_template('room.html', room_id=room_id)

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

@app.route('/logout')
def logout():
    session.pop('username', None)  # Clear the username from session
    session.pop('room_id', None)  # Clear the room ID from session
    session.pop('room_username', None)  # Clear the room username from session
    session.pop('admin_logged_in', None)  # Clear admin login status from session
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
