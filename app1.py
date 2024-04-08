# Import necessary modules and libraries
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import secrets
from uuid import uuid4  # Import uuid4 to generate unique IDs
from flask import flash  # Add this to your imports at the beginning of your Flask app
from flask_migrate import Migrate


# Initialize the Flask app
app = Flask(__name__)
app.secret_key = '333'

# Configure the database URI and other settings
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cab_sharing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'muskart27@gmail.com'
app.config['MAIL_PASSWORD'] = 'jmha dtzo ytjo gnwm'

# Initialize the SQLAlchemy database and the Mail extension
db = SQLAlchemy(app)
mail = Mail(app)

# After initializing your Flask app and SQLAlchemy db
migrate = Migrate(app, db)

# Define the database models
class TemporaryLogin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)

class VerificationToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    token = db.Column(db.String(100), nullable=False)

class CabRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    time = db.Column(db.DateTime, nullable=False)
    verified = db.Column(db.Boolean, default=False)
    creator_email = db.Column(db.String(120), nullable=False)

participants = db.Table('participants',
    db.Column('cab_request_id', db.Integer, db.ForeignKey('cab_request.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    
class JoinRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cab_request_id = db.Column(db.Integer, db.ForeignKey('cab_request.id'), nullable=False)
    requester_email = db.Column(db.String(120), nullable=False)
    accepted = db.Column(db.Boolean, default=False)  # Add this line
    cab_request = db.relationship('CabRequest', backref=db.backref('join_requests', lazy=True))

    
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone_number = request.form['phone']
        
        session['user_name'] = name
        session['user_email'] = email
        session['user_phone'] = phone_number
        
        temp_login = TemporaryLogin(name=name, email=email, phone_number=phone_number)
        db.session.add(temp_login)
        db.session.commit()
        
        token = secrets.token_urlsafe()
        
        # Check if a token already exists for the given email and update it
        verification_token = VerificationToken.query.filter_by(email=email).first()
        if verification_token:
            verification_token.token = token
        else:
            verification_token = VerificationToken(email=email, token=token)
            db.session.add(verification_token)
        
        db.session.commit()

        verification_url = url_for('verify_email', token=token, _external=True)
        msg = Message("Email Verification", sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Please click on the link to verify your email: {verification_url}'
        mail.send(msg)

        return render_template('verify_email_prompt.html')
    
    return render_template('login.html')

@app.route('/verify_email/<token>')
def verify_email(token):
    verification_record = VerificationToken.query.filter_by(token=token).first()
    if verification_record:
        temp_login = TemporaryLogin.query.filter_by(email=verification_record.email).first()
        if temp_login:
            new_user = User.query.filter_by(email=temp_login.email).first()
            if not new_user:
                new_user = User(name=temp_login.name, email=temp_login.email)
                db.session.add(new_user)
            
            cab_requests = CabRequest.query.filter_by(email=verification_record.email, verified=False).all()
            for request in cab_requests:
                request.verified = True
            
            db.session.commit()

            session['logged_in'] = True
            session['user_name'] = temp_login.name
            session['user_email'] = temp_login.email

            return redirect(url_for('home_page'))

    return render_template('verification_failed.html')

@app.route('/home')
def home_page():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('home.html')
@app.route('/request', methods=['GET', 'POST'])
def cab_request():
    if request.method == 'POST':
        name = session.get('user_name')
        email = session.get('user_email')
        phone_number = session.get('user_phone')
        destination = request.form.get('destination')
        date = request.form.get('date')
        time = request.form.get('time')
        datetime_combined = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')

        # Retrieve creator_email from session
        creator_email = email
        
        trip_id = str(uuid4())

        # Check if the user is the creator of the trip
        if email != creator_email:
            # Create a new trip
            new_request = CabRequest(name=name, email=email, phone_number=phone_number, destination=destination, time=datetime_combined, creator_email=creator_email)
            db.session.add(new_request)
            db.session.commit()
            return redirect(url_for('filter_requests', date=date, time_slot=time))
        
        # Check if the user already has an existing trip
        existing_trip = CabRequest.query.filter_by(email=email).first()

        if existing_trip:
            # If the user has an existing trip, allow them to delete it and create a new one
            if request.form.get('delete_trip'):
                db.session.delete(existing_trip)
                db.session.commit()
            else:
                # Redirect to options page to handle the existing trip
                return render_template('options.html', existing_trip=existing_trip)

        # Create a new trip
        new_request = CabRequest(name=name, email=email, phone_number=phone_number, destination=destination, time=datetime_combined, creator_email=creator_email)
        db.session.add(new_request)
        db.session.commit()
        return redirect(url_for('filter_requests', date=date, time_slot=time))

    return render_template('request.html')

@app.route('/requests')
def list_requests():
    requests = CabRequest.query.all()
    return render_template('requests.html', requests=requests)

@app.route('/available')
def available_requests():
    requests = CabRequest.query.filter_by(verified=True).all()
    return render_template('available.html', requests=requests)

@app.route('/filter', methods=['GET', 'POST'])
def filter_requests():
    if request.method == 'POST':
        selected_date = request.form.get('date')
        selected_time_slot = request.form.get('time_slot')
        
        # Parse selected date and time slot
        start_time = datetime.strptime(f"{selected_date} {selected_time_slot}", '%Y-%m-%d %H:%M')
        end_time = start_time + timedelta(minutes=30)  # Calculate end time for the time slot

        # Filter requests by the specified time slot
        filtered_requests = CabRequest.query.filter(
            CabRequest.time >= start_time,
            CabRequest.time < end_time,
            CabRequest.verified == True
        ).all()

        # Check if there are existing trips for the selected time slot
        existing_trips = filtered_requests

        # Render a version of the requests template specific to the selected time slot
        return render_template('requests.html', requests=existing_trips, selected_date=selected_date, selected_time_slot=selected_time_slot)

    # Handle GET request if needed
    return redirect(url_for('home_page'))  # Redirect to home page or handle differently as needed

@app.route('/logout')
def logout():
    # Redirect the user to the home page
    return redirect(url_for('home_page'))

def get_creator_email(trip_id):
    trip = CabRequest.query.filter_by(id=trip_id).first()
    if trip:
        return trip.creator_email
    else:
        return None  # Or handle the case when the trip ID is not found
    
@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    user_email = session['user_email']

    # Trips the user has created
    created_trips = CabRequest.query.filter_by(creator_email=user_email).all()

    # Join requests the user has made to other trips
    sent_requests = JoinRequest.query.filter_by(requester_email=user_email).all()

    # Debugging to see what trips are being fetched
    for trip in created_trips:
        print(trip.id, trip.destination)  # Example of logging trip details

    # Join requests received for the user's trips
    received_requests = []
    for trip in created_trips:
        for join_request in trip.join_requests:
            received_requests.append(join_request)

    # Ensure 'created_trips' is also passed to the template here
    return render_template('dashboard.html', created_trips=created_trips, sent_requests=sent_requests, received_requests=received_requests)

@app.route('/join_trip/<int:cab_request_id>', methods=['POST'])
def join_trip(cab_request_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    user_email = session['user_email']
    existing_request = JoinRequest.query.filter_by(cab_request_id=cab_request_id, requester_email=user_email).first()
    
    if not existing_request:
        join_request = JoinRequest(cab_request_id=cab_request_id, requester_email=user_email)
        db.session.add(join_request)
        db.session.commit()
    
    return redirect(url_for('list_requests'))  # Redirect back to the requests list


@app.route('/handle_join_request/<int:join_request_id>/<action>', methods=['POST'])
def handle_join_request(join_request_id, action):
    if 'logged_in' not in session or not session['logged_in']:
        flash('You need to log in first.', 'warning')
        return redirect(url_for('login'))

    join_request = JoinRequest.query.get(join_request_id)
    if not join_request:
        flash('Join request not found.', 'error')
        return redirect(url_for('dashboard'))

    if action == 'accept':
        # Mark the join request as accepted
        join_request.accepted = True
        flash('Request accepted. User added to the trip.', 'success')
        db.session.commit()
    elif action == 'decline':
        db.session.delete(join_request)
        flash('Request declined.', 'success')
        db.session.commit()

    return redirect(url_for('dashboard'))
