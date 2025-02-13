from app import create_app, db

app = create_app()



if __name__ == "__main__":
    app.run(debug=True)# Run the app 
from flask import Flask

app = Flask(__name__)

# Set a secret key for CSRF protection
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this to a strong, random key