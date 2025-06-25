from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from flask import session, redirect, url_for
from dotenv import load_dotenv
import markdown


load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") 

# Set your API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # Replace with your actual Gemini API key

# Initialize Gemini model
model = genai.GenerativeModel("gemini-2.5-flash")

# Config for DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_history.db'
db = SQLAlchemy(app)

# DB Model
class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(150))  # later used for login
    sender = db.Column(db.String(10))  # 'user' or 'bot'
    message = db.Column(db.Text)

# Initialize DB (only once)
with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))

with app.app_context():
    db.create_all()


# Define chatbot's behavior
system_prompt = """
You are a kind and supportive mental health assistant.
Only answer questions related to emotional well-being, stress, anxiety, depression, mindfulness, and self-care.
Support user if they are feeling down or anxious, and provide helpful resources or coping strategies.
If user wants to say something about their day, encourage them to share their feelings.
If they ask for advice, provide general tips on mental health.
If a user asks something unrelated, politely remind them to stay on topic.
"""


chat = model.start_chat(history=[
    {"role": "user", "parts": [system_prompt]}
])

# @app.route('/')
# def home():
#     return render_template('index.html')

@app.route('/')
def landing():
    return render_template("landing.html")


@app.route('/chat')
@login_required
def chat_home():
    history = ChatHistory.query.filter_by(user=current_user.username).all()
    return render_template('index.html', username=current_user.username, history=history)

@app.route('/chat', methods=['POST'])
@login_required
def chat_reply():
    user_input = request.json.get('message')
    if not user_input:
        return jsonify({'reply': "Please enter a message."})

    db.session.add(ChatHistory(user=current_user.username, sender="user", message=user_input))

    response = chat.send_message(user_input)
    raw_reply = response.text.strip()
    
    # Convert plain text reply to HTML for frontend display
    reply_html = markdown.markdown(raw_reply)

    # Save only raw plain reply to database
    db.session.add(ChatHistory(user=current_user.username, sender="bot", message=raw_reply))
    db.session.commit()

    return jsonify({'reply': reply_html})  # Send formatted HTML to frontend


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template("signup.html")  # ✅ show the form
    else:
        data = request.json
        user = User(username=data['username'], password=data['password'])
        db.session.add(user)
        db.session.commit()
        return jsonify({"success": True})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")  # ✅ show the form
    else:
        data = request.json
        user = User.query.filter_by(username=data['username'], password=data['password']).first()
        if user:
            login_user(user)
            return jsonify({"success": True, "redirect": url_for('chat_home')})
        return jsonify({"success": False})

@app.route('/profile')
@login_required
def profile():
    user = current_user.username
    history = ChatHistory.query.filter_by(user=user).all()
    total_msgs = len(history)
    last_msg = history[-1].message if history else "No messages yet."

    return render_template("profile.html", username=user, message_count=total_msgs, last_message=last_msg)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


if __name__ == '__main__':
    app.run(debug=True)
