from app import db, create_app  # Replace 'your_project' with your actual project name

# Create the app instance
app = create_app()

# Use the app context to access the database and create tables
with app.app_context():
    db.create_all()  # Creates all tables based on models defined
    print("Database tables have been created in bmdb.")
