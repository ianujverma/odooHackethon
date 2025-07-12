
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stackit.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='author', lazy=True)
    answers = db.relationship('Answer', backref='author', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

question_tags = db.Table('question_tags',
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    answers = db.relationship('Answer', backref='question', lazy=True)
    tags = db.relationship('Tag', secondary=question_tags, lazy='subquery',
                          backref=db.backref('questions', lazy=True))

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_accepted = db.Column(db.Boolean, default=False)
    votes = db.Column(db.Integer, default=0)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id'), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # 'up' or 'down'

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    questions = Question.query.order_by(Question.created_at.desc()).all()
    return render_template('index.html', questions=questions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tag_names = request.form.getlist('tags')
        
        question = Question(
            title=title,
            content=content,
            user_id=current_user.id
        )
        
        for tag_name in tag_names:
            if tag_name.strip():
                tag = Tag.query.filter_by(name=tag_name.strip()).first()
                if not tag:
                    tag = Tag(name=tag_name.strip())
                    db.session.add(tag)
                question.tags.append(tag)
        
        db.session.add(question)
        db.session.commit()
        
        return redirect(url_for('view_question', id=question.id))
    
    return render_template('ask.html')

@app.route('/question/<int:id>')
def view_question(id):
    question = Question.query.get_or_404(id)
    answers = Answer.query.filter_by(question_id=id).order_by(Answer.votes.desc()).all()
    return render_template('question.html', question=question, answers=answers)

@app.route('/answer/<int:question_id>', methods=['POST'])
@login_required
def submit_answer(question_id):
    content = request.form['content']
    answer = Answer(
        content=content,
        question_id=question_id,
        user_id=current_user.id
    )
    db.session.add(answer)
    
    # Create notification for question author
    question = Question.query.get(question_id)
    if question.user_id != current_user.id:
        notification = Notification(
            user_id=question.user_id,
            message=f"{current_user.username} answered your question: {question.title}"
        )
        db.session.add(notification)
    
    db.session.commit()
    return redirect(url_for('view_question', id=question_id))

@app.route('/vote/<int:answer_id>/<vote_type>')
@login_required
def vote_answer(answer_id, vote_type):
    existing_vote = Vote.query.filter_by(user_id=current_user.id, answer_id=answer_id).first()
    answer = Answer.query.get_or_404(answer_id)
    
    if existing_vote:
        if existing_vote.vote_type != vote_type:
            existing_vote.vote_type = vote_type
            if vote_type == 'up':
                answer.votes += 2
            else:
                answer.votes -= 2
        else:
            db.session.delete(existing_vote)
            if vote_type == 'up':
                answer.votes -= 1
            else:
                answer.votes += 1
    else:
        vote = Vote(user_id=current_user.id, answer_id=answer_id, vote_type=vote_type)
        db.session.add(vote)
        if vote_type == 'up':
            answer.votes += 1
        else:
            answer.votes -= 1
    
    db.session.commit()
    return redirect(url_for('view_question', id=answer.question_id))

@app.route('/accept/<int:answer_id>')
@login_required
def accept_answer(answer_id):
    answer = Answer.query.get_or_404(answer_id)
    if answer.question.author == current_user:
        # Unaccept all other answers for this question
        Answer.query.filter_by(question_id=answer.question_id).update({'is_accepted': False})
        answer.is_accepted = True
        db.session.commit()
    return redirect(url_for('view_question', id=answer.question_id))

@app.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    return jsonify([{
        'message': n.message,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

@app.route('/notification_count')
@login_required
def notification_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
