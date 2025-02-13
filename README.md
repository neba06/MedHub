****MedHub – Medical Devices Management System****

MedHub is a comprehensive web-based application designed to streamline the management of medical devices within healthcare facilities. It allows administrators to assign devices to technicians and engineers, track device status and health, and log activities, all while ensuring secure access and real-time notifications.

****Features****

**Device Management:** Add, edit, assign, and monitor medical devices.

**User Roles:** Admins, technicians, and engineers with role-based access control.

**Device Assignment:** Assign devices to technicians and engineers with ease.

**Status Updates:** Update device status and health conditions in real-time.

**Notifications:** Automated notifications for device assignments and status changes.

**Activity Logs:** Track and log all device-related activities for audit purposes.

**Secure Authentication:** Secure login with Flask-Login.

**Responsive UI:** Clean and responsive web interface built with Bootstrap.

****Tech Stack****

**Backend:** Python, Flask, SQLAlchemy

**Frontend:** HTML, CSS, Bootstrap, JavaScript

**Database:** SQL Server

**Authentication:** Flask-Login

**Notifications:** Custom Notification Manager

**Logging:** Activity logging for all device operations

****Installation****

**Prerequisites**

Python 3.8+

Flask

SQL Server

****Setup Steps****

**_Clone the repository:_**

git clone https://github.com/neba06/MedHub.git

cd MedHub

**_Create and activate a virtual environment:_**

python -m venv venv

source venv/bin/activate  # On Windows use `venv\Scripts\activate`

**_Install dependencies:**

pip install -r requirements.txt

**_Set environment variables:**

export FLASK_APP=run.py

export FLASK_ENV=development


**_Initialize the database:_**

flask db init

flask db migrate -m "Initial migration."

flask db upgrade

_**Run the application:**_

flask run

_**Access the application at:**_

http://127.0.0.1:5000



****Project Structure****

MedHub/

│
├── app/

│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── templates/
│   ├── static/
│   ├── forms.py
│   └── utilities.py

│
├── migrations/

│
├── tests/

│
├── venv/

│
├── run.py

│
├── config.py

│
└── README.md

****Key Routes****

**_Route	Method	Description_**

/assign_device	GET, POST	Assign devices to technicians/engineers

/device/<int:id>/update_status	POST	Update device status and health

/dashboard	GET	Admin dashboard displaying all devices and activities

/login	GET, POST	User login

/logout	GET	User logout

****Security Measures****

Role-based access control with Flask-Login.

Flash messages for user feedback on actions.

Secure session management and authentication.

Admin-only access to sensitive features like device assignment.

**Contributing**

Contributions are welcome! Please fork the repository and submit a pull request with detailed descriptions of changes.

**To-Do:**

Implement automated device health checks.

Add email/SMS notification support.

Integrate advanced search and filtering for devices.

**License**

This project is licensed under the MIT License – see the LICENSE.md file for details.

**Contact**

Developer: [Nebyu Belay]

Email: [nebyubelay06@gmail.com]

GitHub: https://github.com/neba06
