from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    # Delete existing (optional)
    db.drop_all()
    db.create_all()

    user = User(
        username='testuser',
        email='test@example.com',
        first_name='Test',
        last_name='User',
        is_verified=True
    )
    user.set_password('Password123!')
    db.session.add(user)
    db.session.commit()
    print("Test user created: testuser / Password123!")