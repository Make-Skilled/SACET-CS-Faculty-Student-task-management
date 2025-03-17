from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from pymongo import MongoClient
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime, timedelta
from functools import wraps
import re
import os

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
    # Verify user is a student
    if session.get('user_type') != 'student':
        flash('Access denied. Students only.', 'error')
        return redirect(url_for('index'))

    try:
        # Get student data from database
        student = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not student:
            session.clear()
            flash('User not found', 'error')
            return redirect(url_for('login'))
        
        # Get available tasks from tasks_collection
        pipeline = [
            {
                '$match': {
                    'department': student['department'],
                    'status': 'available'
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
        ]
        available_tasks = list(tasks_collection.aggregate(pipeline))

        # Get started tasks
        started_pipeline = [
            {
                '$match': {
                    'student_id': ObjectId(student['_id']),
                    'status': 'in_progress'
                }
            },
            {
                '$lookup': {
                    'from': 'tasks',
                    'localField': 'task_id',
                    'foreignField': '_id',
                    'as': 'task_info'
                }
            },
            {
                '$addFields': {
                    'task_info': {'$arrayElemAt': ['$task_info', 0]}
                }
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'task_info.faculty_id',
                    'foreignField': '_id',
                    'as': 'faculty'
                }
            },
            {
                '$addFields': {
                    'title': '$task_info.title',
                    'description': '$task_info.description',
                    'deadline': '$task_info.deadline',
                    'department': '$task_info.department',
                    'faculty_name': {
                        '$ifNull': [
                            {'$arrayElemAt': ['$faculty.full_name', 0]},
                            'Unknown Faculty'
                        ]
                    }
                }
            },
            {
                '$sort': {'started_at': -1}
            }
        ]
        started_tasks = list(started_tasks_collection.aggregate(started_pipeline))

        # Get completed tasks
        completed_pipeline = [
            {
                '$match': {
                    'student_id': ObjectId(student['_id']),
                    'status': 'completed'
                }
            },
            {
                '$lookup': {
                    'from': 'tasks',
                    'localField': 'task_id',
                    'foreignField': '_id',
                    'as': 'task_info'
                }
            },
            {
                '$addFields': {
                    'task_info': {'$arrayElemAt': ['$task_info', 0]}
                }
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'task_info.faculty_id',
                    'foreignField': '_id',
                    'as': 'faculty'
                }
            },
            {
                '$addFields': {
                    'title': '$task_info.title',
                    'description': '$task_info.description',
                    'deadline': '$task_info.deadline',
                    'department': '$task_info.department',
                    'faculty_name': {
                        '$ifNull': [
                            {'$arrayElemAt': ['$faculty.full_name', 0]},
                            'Unknown Faculty'
                        ]
                    }
                }
            },
            {
                '$sort': {'submitted_at': -1}
            }
        ]
        completed_tasks = list(started_tasks_collection.aggregate(completed_pipeline))

        return render_template('student/dashboard.html',
                             student=student,
                             available_tasks=available_tasks,
                             started_tasks=started_tasks,
                             completed_tasks=completed_tasks)
                             
    except Exception as e:
        print(f"Error in student_dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/dashboard/faculty')
@login_required
@faculty_required
def faculty_dashboard():
    try:
        # Get faculty data from database
        faculty = users_collection.find_one({'_id': ObjectId(session['user_id'])})
        if not faculty:
            session.clear()
            flash('User not found', 'error')
            return redirect(url_for('login'))
        
        # Get all tasks created by this faculty with student information
        pipeline = [
            {
                '$match': {
                    'faculty_id': ObjectId(session['user_id'])
                }
            },
            {
                '$lookup': {
                    'from': 'users',
                    'localField': 'student_id',
                    'foreignField': '_id',
                    'as': 'student'
                }
            },
            {
                '$addFields': {
                    'student_name': {
                        '$ifNull': [
                            {'$arrayElemAt': ['$student.full_name', 0]},
                            None
                        ]
                    }
                }
            },
            {
                '$sort': {'created_at': -1}
            }
        ]
        tasks = list(tasks_collection.aggregate(pipeline))
        
        # Get students in faculty's department
        students = list(users_collection.find({
            'user_type': 'student',
            'department': faculty['department']
        }))

        # Calculate task statistics
        total_tasks = len(tasks)
        available_tasks = sum(1 for task in tasks if task['status'] == 'available')
        pending_tasks = sum(1 for task in tasks if task['status'] == 'pending')
        completed_tasks = sum(1 for task in tasks if task['status'] == 'completed')
        
        return render_template('faculty/dashboard.html', 
                             faculty=faculty,
                             tasks=tasks,
                             students=students,
                             stats={
                                 'total_tasks': total_tasks,
                                 'available_tasks': available_tasks,
                                 'pending_tasks': pending_tasks,
                                 'completed_tasks': completed_tasks
                             })
                             
    except Exception as e:
        print(f"Error in faculty_dashboard: {str(e)}")  # Add logging
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

        # Check if task exists and is available
        task = tasks_collection.find_one({
            '_id': ObjectId(task_id),
            'status': 'available'
        })

        if not task:
            flash('Task not found or already submitted', 'error')
            return redirect(url_for('student_dashboard'))

        # Handle file upload
        if 'task_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('student_dashboard'))

        file = request.files['task_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('student_dashboard'))

        # Create submission document
        submission_data = {
            'task_id': ObjectId(task_id),
            'student_id': ObjectId(session['user_id']),
            'comments': comments,
            'submitted_at': datetime.utcnow(),
            'status': 'completed'
        }

        # Insert submission into started_tasks_collection
        started_tasks_collection.insert_one(submission_data)

        # Update task status
        tasks_collection.update_one(
            {'_id': ObjectId(task_id)},
            {
                '$set': {
                    'status': 'completed',
                    'submitted_by': ObjectId(session['user_id']),
                    'submitted_at': datetime.utcnow()
                }
            }
        )

        flash('Task submitted successfully', 'success')
        return redirect(url_for('student_dashboard'))

    except Exception as e:
        print(f"Error in submit_task: {str(e)}")  # Log the error
        flash('An error occurred while submitting the task', 'error')
        return redirect(url_for('student_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)