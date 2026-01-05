import os
from datetime import datetime
from functools import wraps

from flask import jsonify, render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.main import bp
from app.models import User
from app import db
import analyze


def subscription_required(f):
    """Decorator to require active subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_subscription_active():
            flash('Please subscribe to access this feature.', 'warning')
            return redirect(url_for('main.pricing'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route("/")
@bp.route("/index")
def index():
    """Landing page - shows dashboard if logged in with subscription"""
    if current_user.is_authenticated and current_user.is_subscription_active():
        return redirect(url_for('main.dashboard'))
    return render_template("index.html", title="Trading Analyzer")


@bp.route("/dashboard")
@login_required
@subscription_required
def dashboard():
    """User's personal dashboard"""
    return render_template("dashboard.html", title="Dashboard")


@bp.route("/upload", methods=["GET", "POST"])
@login_required
@subscription_required
def upload():
    """Upload trade history file"""
    if request.method == "POST":
        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return redirect(url_for('main.upload'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('main.upload'))
        
        if file and file.filename.endswith(('.html', '.htm')):
            # Create uploads folder if not exists
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Save with unique filename per user
            filename = f"user_{current_user.id}_history.html"
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Update user record
            current_user.history_file = filename
            current_user.history_uploaded_at = datetime.utcnow()
            db.session.commit()
            
            flash('Trade history uploaded successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Please upload an HTML file.', 'error')
    
    return render_template("upload.html", title="Upload")


@bp.route("/pricing")
def pricing():
    """Pricing page"""
    return render_template("pricing.html", title="Pricing")


@bp.route("/subscribe", methods=["POST"])
@login_required
def subscribe():
    """Handle subscription (demo - instant activation)"""
    from datetime import timedelta
    current_user.is_subscribed = True
    current_user.subscription_end = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash('Subscription activated for 30 days!', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route("/api/data", methods=["GET"])
@login_required
@subscription_required
def api_data():
    """API endpoint for user's trade data"""
    try:
        # Check if user has uploaded a file
        if current_user.history_file:
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            file_path = os.path.join(upload_folder, current_user.history_file)
            if os.path.exists(file_path):
                data = analyze.analyze_user_file(file_path)
                return jsonify(data)
        
        # If admin and no file, try MT5 live data
        if current_user.is_admin:
            return jsonify(analyze.get_trade_data())
        
        return jsonify({"error": "No trade history uploaded. Please upload your MT5 report."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500