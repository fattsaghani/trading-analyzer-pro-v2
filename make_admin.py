from app import db, create_app
from app.models import User

app = create_app()
with app.app_context():
    db.create_all()
    user = User.query.filter_by(email='fatumaaghani@gmail.com').first()
    if user:
        user.is_admin = True
        user.is_subscribed = True
        db.session.commit()
        print("You are now admin!")
    else:
        print("User not found. Register first on the website.")