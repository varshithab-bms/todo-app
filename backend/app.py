from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, jwt, datetime
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.message import EmailMessage
import firebase_admin
from firebase_admin import credentials, messaging

# Initialize Firebase Admin SDK
cred = credentials.Certificate("todo-list-e8834-firebase-adminsdk-fbsvc-d994d73713.json")
firebase_admin.initialize_app(cred)

# App setup
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'supersecretkey'

# Config
EMAIL_ADDRESS = 'youremail@gmail.com'
EMAIL_PASSWORD = 'yourapppassword'
USER_FILE = 'users.json'
TODO_FILE = 'todos.json'
FCM_TOKEN_FILE = 'tokens.json'

# Utilities
def load_json(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def send_email(to, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print("Email sending error:", e)

def send_fcm_notification(token, title, body):
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token
        )
        response = messaging.send(message)
        print('FCM notification sent:', response)
    except Exception as e:
        print("FCM send error:", e)

# Reminder scheduler
def send_reminder_emails():
    todos = load_json(TODO_FILE)
    tokens = load_json(FCM_TOKEN_FILE)
    now = datetime.datetime.now().strftime('%H:%M')

    for user, tasks in todos.items():
        for task in tasks:
            if not task.get("completed") and task.get("reminder") == now:
                subject = "\u23f0 Reminder: " + task['task']
                body = f"You have a task due today: {task['task']}\nDue: {task.get('due_date', 'N/A')}"
                send_email(user, subject, body)
                if user in tokens:
                    send_fcm_notification(tokens[user], subject, body)

scheduler = BackgroundScheduler()
scheduler.add_job(send_reminder_emails, 'interval', minutes=1)
scheduler.start()

# Auth routes
@app.route('/signup', methods=['POST'])
def signup():
    users = load_json(USER_FILE)
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if username in users:
        return jsonify({'error': 'User already exists'}), 400

    users[username] = password
    save_json(USER_FILE, users)
    return jsonify({'message': 'Signup successful'})

@app.route('/login', methods=['POST'])
def login():
    users = load_json(USER_FILE)
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if users.get(username) != password:
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'username': username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token})

def verify_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['username']
    except (jwt.ExpiredSignatureError, jwt.DecodeError):
        return None

# Token registration
@app.route('/register_token', methods=['POST'])
def register_token():
    token_header = request.headers.get('Authorization')
    username = verify_token(token_header)
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    fcm_token = data.get('fcm_token')
    if not fcm_token:
        return jsonify({'error': 'Missing FCM token'}), 400

    tokens = load_json(FCM_TOKEN_FILE)
    tokens[username] = fcm_token
    save_json(FCM_TOKEN_FILE, tokens)

    return jsonify({'message': 'FCM token registered'})

# Todo routes
@app.route('/todos', methods=['POST'])
def add_todo():
    token = request.headers.get('Authorization')
    username = verify_token(token)
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data or 'task' not in data:
        return jsonify({'error': 'Task is required'}), 400

    task_data = {
        'task': data['task'],
        'date': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
        'completed': False,
        'category': data.get('category', 'general'),
        'due_date': data.get('due_date') or datetime.datetime.utcnow().strftime('%Y-%m-%d'),
        'reminder': data.get('reminder')
    }

    all_todos = load_json(TODO_FILE)
    all_todos.setdefault(username, []).append(task_data)
    save_json(TODO_FILE, all_todos)
    return jsonify({'message': 'Todo added'}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
    token = request.headers.get('Authorization')
    username = verify_token(token)
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    user_todos = load_json(TODO_FILE).get(username, [])
    categorized = {}
    for index, todo in enumerate(user_todos):
        cat = todo.get('category', 'general')
        if cat not in categorized:
            categorized[cat] = {'active': [], 'completed': []}
        entry = todo.copy()
        entry['index'] = index
        if todo.get('completed'):
            categorized[cat]['completed'].append(entry)
        else:
            categorized[cat]['active'].append(entry)

    return jsonify(categorized)

@app.route('/todos/complete/<int:index>', methods=['POST'])
def complete_todo(index):
    token = request.headers.get('Authorization')
    username = verify_token(token)
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    all_todos = load_json(TODO_FILE)
    user_todos = all_todos.get(username, [])

    if 0 <= index < len(user_todos):
        user_todos[index]['completed'] = True
        save_json(TODO_FILE, all_todos)
        return jsonify({'message': 'Marked as completed'})
    return jsonify({'error': 'Invalid index'}), 404

@app.route('/todos/<int:index>', methods=['DELETE'])
def delete_todo(index):
    token = request.headers.get('Authorization')
    username = verify_token(token)
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    all_todos = load_json(TODO_FILE)
    user_todos = all_todos.get(username, [])
    if 0 <= index < len(user_todos):
        user_todos.pop(index)
        all_todos[username] = user_todos
        save_json(TODO_FILE, all_todos)
        return jsonify({'message': 'Todo deleted'})
    return jsonify({'error': 'Invalid index'}), 404

# Ensure file existence
def ensure_files_exist():
    for file in [USER_FILE, TODO_FILE, FCM_TOKEN_FILE]:
        if not os.path.exists(file):
            save_json(file, {})

if __name__ == '__main__':
    ensure_files_exist()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

