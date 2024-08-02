from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
import os
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for flash messages and session management
socketio = SocketIO(app)

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
        if username:
            session['username'] = username
            return redirect(url_for('room_options'))
        flash("Username is required.", "error")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)  # Clear the username from session
    session.pop('room_id', None)  # Clear the room ID from session
    session.pop('room_name', None)  # Clear the room name from session
    session.pop('admin_logged_in', None)  # Clear admin login status from session
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

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

    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')

    if not (name and username and password):
        flash("All fields are required.", "error")
        return redirect(url_for('view_database'))

    conn = get_db()
    try:
        conn.execute('INSERT INTO users (name, username, password) VALUES (?, ?, ?)',
                     (name, username, password))
        conn.commit()
        flash("User added successfully!", "success")
    except sqlite3.IntegrityError:
        flash("Username already exists.", "error")
    finally:
        conn.close()

    return redirect(url_for('view_database'))

@app.route('/room_options')
def room_options():
    if 'username' not in session and 'admin_logged_in' not in session:
        flash("You need to log in first.", "error")
        return redirect(url_for('login'))
    return render_template('room_options.html')

@app.route('/room_input', methods=['POST'])
def room_input():
    action = request.form.get('action')
    room_id = request.form.get('room_id')
    room_name = request.form.get('room_name')

    if action == 'join':
        if not room_id:
            flash("Room ID is required.", "error")
            return render_template('room_options.html')
        session['room_id'] = room_id
        return redirect(url_for('room', room_id=room_id))
    
    elif action == 'create':
        if not room_name:
            flash("Room Name is required.", "error")
            return render_template('room_options.html')
        
        room_id = str(uuid.uuid4())  # Generate a unique room ID
        session['room_id'] = room_id
        session['room_name'] = room_name
        flash(f"Room created successfully! Room ID: {room_id}", "success")
        return redirect(url_for('room', room_id=room_id))
    
    flash("Invalid action.", "error")
    return render_template('room_options.html')

@app.route('/room/<room_id>')
def room(room_id):
    if 'username' not in session:
        flash("You need to log in first.", "error")
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

# WebSocket Events
@socketio.on('message')
def handle_message(data):
    room_id = data.get('room_id')
    message = data.get('message')
    username = session.get('username', 'Unknown User')  # Ensure the username is retrieved from session
    if room_id:
        emit('message', {'username': username, 'message': message}, room=room_id)

@socketio.on('join')
def on_join(data):
    room_id = data.get('room_id')
    if room_id:
        join_room(room_id)
        username = session.get('username', 'Unknown User')  # Retrieve the username from the session
        emit('status', {'username': username, 'message': 'has joined the room.'}, room=room_id)

@socketio.on('leave')
def on_leave(data):
    room_id = data.get('room_id')
    if room_id:
        leave_room(room_id)
        username = session.get('username', 'Unknown User')  # Retrieve the username from the session
        emit('status', {'username': username, 'message': 'has left the room.'}, room=room_id)

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
