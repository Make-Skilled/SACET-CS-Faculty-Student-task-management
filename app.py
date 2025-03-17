from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime, timedelta
from functools import wraps
import re
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'TaskManagementSystem@$k'

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB limit

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# MongoDB configuration
client = MongoClient('mongodb+srv://kr4785543:1234567890@cluster0.220yz.mongodb.net/')
db = client['task_management_system']
users_collection = db['users']
tasks_collection = db['tasks']
started_tasks_collection = db['started_tasks']
submissions_collection = db['submissions']  # New collection for submissions

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "kr4785543@gmail.com"  # Replace with your email
SMTP_PASSWORD = "qhuzwfrdagfyqemk"     # Replace with your app password   # Replace with your app password

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Faculty required decorator
def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_type' not in session or session['user_type'] != 'faculty':
            flash('Access denied. Faculty only.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        remember = request.form.get('remember-me')
        
        try:
            # Validate required fields
            if not all([email, password, user_type]):
                flash('All fields are required', 'error')
                return redirect(url_for('login'))
            
            # Validate email format
            if not is_valid_email(email):
                flash('Invalid email format', 'error')
                return redirect(url_for('login'))
            
            # Find user by email and user type
            user = users_collection.find_one({
                'email': email,
                'user_type': user_type
            })
            
            if not user:
                flash(f'No {user_type} account found with this email', 'error')
                return redirect(url_for('login'))
            
            if not check_password_hash(user['password'], password):
                flash('Invalid password', 'error')
                return redirect(url_for('login'))
            
            # Set session data
            session['user_id'] = str(user['_id'])
            session['user_type'] = user['user_type']
            session['full_name'] = user['full_name']
            session['email'] = user['email']
            
            # Set additional session data based on user type
            if user_type == 'student':
                session['student_id'] = user['student_id']
                session['department'] = user['department']
            else:  # faculty
                session['faculty_id'] = user['faculty_id']
                session['department'] = user['department']
            
            # Handle remember me functionality
            if remember:
                # Set session to permanent and lifetime to 30 days
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            
            # Redirect based on user type
            if user_type == 'faculty':
                flash(f'Welcome back, {user["full_name"]}!', 'success')
                return redirect(url_for('faculty_dashboard'))
            else:  # student
                flash(f'Welcome back, {user["full_name"]}!', 'success')
                return redirect(url_for('student_dashboard'))
                
        except Exception as e:
            flash('An error occurred during login. Please try again.', 'error')
            return redirect(url_for('login'))
    
    # If user is already logged in, redirect to appropriate dashboard
    if 'user_id' in session:
        if session['user_type'] == 'faculty':
            return redirect(url_for('faculty_dashboard'))
        return redirect(url_for('student_dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/register/student', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        try:
            # Get form data
            full_name = request.form.get('full_name')
            student_id = request.form.get('student_id')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            department = request.form.get('department')
            
            # Validate required fields
            if not all([full_name, student_id, email, password, confirm_password, department]):
                flash('All fields are required', 'error')
                return redirect(url_for('student_register'))
            
            # Validate email format
            if not is_valid_email(email):
                flash('Invalid email format', 'error')
                return redirect(url_for('student_register'))
            
            # Check if email already exists
            if users_collection.find_one({'email': email}):
                flash('Email already registered', 'error')
                return redirect(url_for('student_register'))
            
            # Check if student ID already exists
            if users_collection.find_one({'student_id': student_id}):
                flash('Student ID already registered', 'error')
                return redirect(url_for('student_register'))
            
            # Validate password match
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('student_register'))
            
            # Create student document
            student_data = {
                'user_type': 'student',
                'full_name': full_name,
                'student_id': student_id,
                'email': email,
                'password': generate_password_hash(password),
                'department': department,
                'created_at': datetime.utcnow()
            }
            
            # Insert student into database
            users_collection.insert_one(student_data)
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('An error occurred during registration', 'error')
            return redirect(url_for('student_register'))
    
    return render_template('student_register.html')

@app.route('/register/faculty', methods=['GET', 'POST'])
def faculty_register():
    if request.method == 'POST':
        try:
            # Get form data
            full_name = request.form.get('full_name')
            faculty_id = request.form.get('faculty_id')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            department = request.form.get('department')
            
            # Validate required fields
            if not all([full_name, faculty_id, email, password, confirm_password, department]):
                flash('All fields are required', 'error')
                return redirect(url_for('faculty_register'))
            
            # Validate email format
            if not is_valid_email(email):
                flash('Invalid email format', 'error')
                return redirect(url_for('faculty_register'))
            
            # Check if email already exists
            if users_collection.find_one({'email': email}):
                flash('Email already registered', 'error')
                return redirect(url_for('faculty_register'))
            
            # Check if faculty ID already exists
            if users_collection.find_one({'faculty_id': faculty_id}):
                flash('Faculty ID already registered', 'error')
                return redirect(url_for('faculty_register'))
            
            # Validate password match
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return redirect(url_for('faculty_register'))
            
            # Create faculty document
            faculty_data = {
                'user_type': 'faculty',
                'full_name': full_name,
                'faculty_id': faculty_id,
                'email': email,
                'password': generate_password_hash(password),
                'department': department,
                'created_at': datetime.utcnow()
            }
            
            # Insert faculty into database
            users_collection.insert_one(faculty_data)
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('An error occurred during registration', 'error')
            return redirect(url_for('faculty_register'))
    
    return render_template('faculty_register.html')

@app.route('/dashboard/student')
@login_required
def student_dashboard():
    try:
        student_id = ObjectId(session['user_id'])
        
        # Get student data from database
        student = users_collection.find_one({'_id': student_id})
        if not student:
            session.clear()
            flash('User not found', 'error')
            return redirect(url_for('login'))

        # Get tasks that the student hasn't started yet
        available_tasks = list(tasks_collection.aggregate([
            {
                '$match': {
                    'department': student['department']
                }
            },
            {
                '$lookup': {
                    'from': 'started_tasks',
                    'let': { 'taskId': '$_id' },
                    'pipeline': [
                        {
                            '$match': {
                                '$expr': {
                                    '$and': [
                                        { '$eq': ['$task_id', '$$taskId'] },
                                        { '$eq': ['$student_id', student_id] }
                                    ]
                                }
                            }
                        }
                    ],
                    'as': 'started'
                }
            },
            {
                '$match': {
                    'started': { '$size': 0 }
                }
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'faculty_id',
                    'foreignField': '_id',
                    'as': 'faculty'
                }
            },
            {
                '$addFields': {
                    'faculty_name': {
                        '$ifNull': [
                            {'$arrayElemAt': ['$faculty.full_name', 0]},
                            'Unknown Faculty'
                        ]
                    }
                }
            },
            {
                '$sort': {'deadline': 1}
            }
        ]))

        # Get tasks that are in progress (started but not completed)
        started_tasks = list(started_tasks_collection.aggregate([
            {
                '$match': {
                    'student_id': student_id,
                    'status': {'$nin': ['completed', 'submitted']}
                }
            },
            {
                '$lookup': {
                    'from': 'tasks',
                    'localField': 'task_id',
                    'foreignField': '_id',
                    'as': 'task'
                }
            },
            {
                '$unwind': '$task'
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'task.faculty_id',
                    'foreignField': '_id',
                    'as': 'faculty'
                }
            },
            {
                '$project': {
                    'title': '$task.title',
                    'description': '$task.description',
                    'faculty_name': {
                        '$ifNull': [
                            {'$arrayElemAt': ['$faculty.full_name', 0]},
                            'Unknown Faculty'
                        ]
                    },
                    'deadline': '$task.deadline',
                    'status': 1,
                    '_id': 1
                }
            }
        ]))

        # Get completed/submitted tasks
        completed_tasks = list(started_tasks_collection.aggregate([
            {
                '$match': {
                    'student_id': student_id,
                    'status': {'$in': ['completed', 'submitted']}
                }
            },
            {
                '$lookup': {
                    'from': 'tasks',
                    'localField': 'task_id',
                    'foreignField': '_id',
                    'as': 'task'
                }
            },
            {
                '$unwind': '$task'
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'task.faculty_id',
                    'foreignField': '_id',
                    'as': 'faculty'
                }
            },
            {
                '$project': {
                    'title': '$task.title',
                    'faculty_name': {
                        '$ifNull': [
                            {'$arrayElemAt': ['$faculty.full_name', 0]},
                            'Unknown Faculty'
                        ]
                    },
                    'submitted_at': 1,
                    'status': 1,
                    'grade': 1,
                    'comments': 1,
                    'file_path': 1
                }
            },
            {
                '$sort': {'submitted_at': -1}
            }
        ]))

        # Calculate statistics
        stats = {
            'available': len(available_tasks),
            'in_progress': len(started_tasks),
            'completed': len(completed_tasks),
            'total_tasks': len(available_tasks) + len(started_tasks) + len(completed_tasks)
        }

        return render_template('student/dashboard.html',
                             student=student,
                             available_tasks=available_tasks,
                             started_tasks=started_tasks,
                             completed_tasks=completed_tasks,
                             stats=stats)

    except Exception as e:
        print(f"Error in student_dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/dashboard/faculty')
@login_required
@faculty_required
def faculty_dashboard():
    try:
        faculty_id = ObjectId(session['user_id'])
        
        # Get faculty data
        faculty = users_collection.find_one({'_id': faculty_id})
        if not faculty:
            session.clear()
            flash('User not found', 'error')
            return redirect(url_for('login'))
        
        # Get all tasks by this faculty
        faculty_tasks = list(tasks_collection.find({
            'faculty_id': faculty_id
        }).sort('created_at', -1))  # Sort by newest first
        
        # Get all submissions
        submissions = list(started_tasks_collection.find({
            'task_id': {'$in': [task['_id'] for task in faculty_tasks]},
            'status': {'$in': ['completed', 'submitted']}
        }))
        
        # Enhance submissions with task and student details
        enhanced_submissions = []
        for submission in submissions:
            task = tasks_collection.find_one({'_id': submission['task_id']})
            student = users_collection.find_one({'_id': submission['student_id']})
            if task and student:
                enhanced_submissions.append({
                    'task_title': task['title'],
                    'student_name': student['full_name'],
                    'student_email': student['email'],
                    'submitted_at': submission['submitted_at'],
                    'status': submission['status'],
                    'grade': submission.get('grade'),
                    'feedback': submission.get('feedback'),
                    'task_total_marks': task['total_marks'],
                    'file_path': submission.get('file_path'),
                    '_id': submission['_id']
                })
        
        # Calculate statistics
        stats = {
            'total_tasks': len(faculty_tasks),
            'total_submissions': len(enhanced_submissions),
            'pending_review': len([s for s in enhanced_submissions if not s.get('grade')]),
            'graded': len([s for s in enhanced_submissions if s.get('grade')])
        }
        
        # Get today's date for the deadline input min attribute
        today = datetime.utcnow().strftime('%Y-%m-%d')
        
        return render_template('faculty/dashboard.html',
                             faculty=faculty,
                             tasks=faculty_tasks,
                             all_submissions=enhanced_submissions,
                             stats=stats,
                             today=today)

    except Exception as e:
        print(f"Error in faculty_dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/task/add', methods=['POST'])
@login_required
@faculty_required
def add_task():
    try:
        # Get form data
        title = request.form.get('title')
        description = request.form.get('description')
        deadline = request.form.get('deadline')
        total_marks = request.form.get('total_marks')
        
        # Validate required fields
        if not all([title, description, deadline, total_marks]):
            flash('All fields are required', 'error')
            return redirect(url_for('faculty_dashboard'))
        
        try:
            total_marks = int(total_marks)
            if total_marks < 0 or total_marks > 100:
                flash('Total marks must be between 0 and 100', 'error')
                return redirect(url_for('faculty_dashboard'))
        except ValueError:
            flash('Total marks must be a valid number', 'error')
            return redirect(url_for('faculty_dashboard'))
        
        # Create task document
        task_data = {
            'title': title,
            'description': description,
            'deadline': datetime.strptime(deadline, '%Y-%m-%d'),
            'status': 'available',
            'faculty_id': ObjectId(session['user_id']),
            'department': session['department'],
            'total_marks': total_marks,
            'created_at': datetime.utcnow()
        }
        
        # Insert task into database
        tasks_collection.insert_one(task_data)
        
        flash('Task added successfully', 'success')
        return redirect(url_for('faculty_dashboard'))
        
    except Exception as e:
        print(f"Error in add_task: {str(e)}")  # Add logging
        flash('An error occurred while adding the task', 'error')
        return redirect(url_for('faculty_dashboard'))

@app.route('/task/submit', methods=['POST'])
@login_required
def submit_task():
    try:
        task_id = request.form.get('task_id')
        comments = request.form.get('comments', '')

        # Validate task_id
        if not task_id:
            flash('Invalid task ID', 'error')
            return redirect(url_for('student_dashboard'))

        # Check if task exists and get task details
        task = tasks_collection.find_one({
            '_id': ObjectId(task_id)
        })

        if not task:
            flash('Task not found', 'error')
            return redirect(url_for('student_dashboard'))

        # Get faculty details
        faculty = users_collection.find_one({
            '_id': task['faculty_id']
        })

        if not faculty:
            flash('Faculty not found', 'error')
            return redirect(url_for('student_dashboard'))

        # Get student details
        student = users_collection.find_one({
            '_id': ObjectId(session['user_id'])
        })

        # Handle file upload
        if 'task_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('student_dashboard'))

        file = request.files['task_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('student_dashboard'))

        if file and allowed_file(file.filename):
            # Generate a secure filename with timestamp
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            final_filename = f"{session['user_id']}_{timestamp}_{filename}"
            
            # Save the file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
            file.save(file_path)

            # Create submission document
            submission_data = {
                'task_id': ObjectId(task_id),
                'student_id': ObjectId(session['user_id']),
                'comments': comments,
                'submitted_at': datetime.utcnow(),
                'status': 'submitted',
                'file_path': final_filename
            }

            # Insert or update submission in started_tasks_collection
            result = started_tasks_collection.update_one(
                {
                    'task_id': ObjectId(task_id),
                    'student_id': ObjectId(session['user_id'])
                },
                {'$set': submission_data},
                upsert=True
            )

            if result.modified_count > 0 or result.upserted_id:
                # Send email notification to faculty
                notification_sent = send_submission_notification(
                    task_id=task_id,
                    student_name=student['full_name'],
                    task_title=task['title'],
                    faculty_email=faculty['email']
                )
                
                if notification_sent:
                    flash('Task submitted successfully and faculty notified', 'success')
                else:
                    flash('Task submitted successfully but faculty notification failed', 'warning')
            else:
                flash('Error submitting task', 'error')

            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid file type. Please upload PDF or Word document.', 'error')
            return redirect(url_for('student_dashboard'))

    except Exception as e:
        print(f"Error in submit_task: {str(e)}")
        flash('An error occurred while submitting the task', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/uploads/<filename>')
@login_required
def download_file(filename):
    try:
        # Check if user has permission to access this file
        submission = started_tasks_collection.find_one({
            'file_path': filename
        })
        
        if not submission:
            flash('File not found', 'error')
            return redirect(url_for('student_dashboard'))
            
        # Check if user is either the student who submitted or the faculty who created the task
        if str(submission['student_id']) != session['user_id'] and session['user_type'] != 'faculty':
            flash('Access denied', 'error')
            return redirect(url_for('student_dashboard'))
            
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
        
    except Exception as e:
        print(f"Error in download_file: {str(e)}")
        flash('Error downloading file', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/submission/evaluate', methods=['POST'])
@login_required
@faculty_required
def evaluate_submission():
    try:
        submission_id = request.form.get('submission_id')
        grade = request.form.get('grade')
        feedback = request.form.get('feedback', '')

        # Validate inputs
        if not submission_id or not grade:
            flash('Missing required fields', 'error')
            return redirect(url_for('faculty_dashboard'))

        try:
            grade = int(grade)
            if grade < 0 or grade > 100:
                flash('Grade must be between 0 and 100', 'error')
                return redirect(url_for('faculty_dashboard'))
        except ValueError:
            flash('Invalid grade value', 'error')
            return redirect(url_for('faculty_dashboard'))

        # Update the submission
        result = started_tasks_collection.update_one(
            {'_id': ObjectId(submission_id)},
            {
                '$set': {
                    'grade': grade,
                    'feedback': feedback,
                    'status': 'completed',
                    'graded_at': datetime.utcnow(),
                    'graded_by': ObjectId(session['user_id'])
                }
            }
        )

        if result.modified_count > 0:
            flash('Submission graded successfully', 'success')
        else:
            flash('Submission not found or already graded', 'error')

        return redirect(url_for('faculty_dashboard'))

    except Exception as e:
        print(f"Error in evaluate_submission: {str(e)}")
        flash('An error occurred while evaluating the submission', 'error')
        return redirect(url_for('faculty_dashboard'))

def send_email(subject, body, recipient_email):
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Add body to email
        msg.attach(MIMEText(body, 'plain'))

        # Create SMTP session
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            
            # Send email
            server.send_message(msg)
            
        print(f"Email sent successfully to: {recipient_email}")
        return True

    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

def send_submission_notification(task_id, student_name, task_title, faculty_email):
    try:
        submission_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
        subject = f'New Submission: {task_title}'
        body = f"""
Dear Faculty,

A new submission has been received for your task.

Submission Details:
- Task: {task_title}
- Student: {student_name}
- Submitted on: {submission_time}

Please log in to the Task Management System to review and grade the submission.

Best regards,
Task Management System Team
        """

        return send_email(subject, body, faculty_email)

    except Exception as e:
        print(f"Error preparing submission notification: {str(e)}")
        return False

if __name__ == '__main__':
    app.run(debug=True)