def format_datetime(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def send_reminder(reminder):
    # Logic to send reminder
    pass

from .models import ActivityLog, User, Notification, Device
from . import db
from flask_login import current_user
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from datetime import datetime


def log_activity(user, action, device=None):
    """Log user activity with optional device context."""
    user_id = None
    
    # Extract user_id from the user object or use the provided ID
    if isinstance(user, User):
        user_id = user.id
    elif isinstance(user, int):
        user_id = user
    else:
        print("Invalid user object or user ID passed to log_activity function.")
        return

    # Get the device_id if a device is provided
    device_id = device.id if isinstance(device, Device) else None

    # Log the activity
    if user_id:
        new_log = ActivityLog(
            user_id=user_id,
            action=action,
            timestamp=datetime.utcnow(),
            device_id=device_id  # Associate the device with the activity
        )
        db.session.add(new_log)
        db.session.commit()
    else:
        print("Failed to log activity: No valid user ID.")

from datetime import datetime, timedelta
from .models import Task, db  # Adjust imports based on your project structure

def create_maintenance_tasks(device, current_user):
    """Automatically create maintenance tasks for a device based on its schedule."""
    schedule_mapping = {
        'Daily': (1, 'Low'),
        'Weekly': (7, 'Medium'),
        'Monthly': (30, 'Medium'),
        'Quarterly': (90, 'High'),
        'Yearly': (365, 'Critical'),
    }

    schedules = device.maintenance_schedule.split(', ')
    today = datetime.utcnow()

    for schedule in schedules:
        interval_days, priority = schedule_mapping.get(schedule, (None, 'Medium'))
        if interval_days:
            due_date = today + timedelta(days=interval_days)

            task = Task(
                title=f'{schedule} Maintenance for {device.name}',
                description=f'{schedule} maintenance task for {device.name}.',
                device_id=device.id,
                created_by=current_user.id,  # Pass current_user.id here
                priority=priority,  # Priority based on schedule
                due_date=due_date,
                status='Not Started',
                assigned_to=None,  # Unassigned
            )
            db.session.add(task)

    db.session.commit()

from sqlalchemy.sql import text

class NotificationManager:
    @staticmethod
    def add_notification(user_id, message, notif_type, task_id=None, device_id=None, incident_id=None, assigned_user_id=None):
        """
        Add a notification using SQL Server query.
        """
        sql_query = """
        INSERT INTO notification 
        (user_id, message, type, task_id, device_id, incident_id, assigned_user_id, timestamp, is_read) 
        VALUES 
        (:user_id, :message, :notif_type, :task_id, :device_id, :incident_id, :assigned_user_id, :timestamp, :is_read);
        """
        values = {
            "user_id": user_id,
            "message": message,
            "notif_type": notif_type,
            "task_id": task_id,
            "device_id": device_id,
            "incident_id": incident_id,
            "assigned_user_id": assigned_user_id,
            "timestamp": datetime.utcnow(),
            "is_read": False
        }
        db.session.execute(text(sql_query), values)
        db.session.commit()

    @staticmethod
    def get_user_notifications(user_id, limit=10, offset=0):
        """
        Fetch recent notifications for a user using SQL Server query.
        """
        sql_query = """
        SELECT n.*, u.username AS assigned_username
        FROM notification n
        LEFT JOIN peoples u ON n.assigned_user_id = u.id
        WHERE n.user_id = :user_id
        ORDER BY n.timestamp DESC
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY;
        """
        result = db.session.execute(
            text(sql_query),
            {"user_id": user_id, "limit": limit, "offset": offset}
        )
        return result.fetchall()

    @staticmethod
    def mark_as_read(notification_id):
        """
        Mark a notification as read using SQL Server query.
        """
        sql_query = """
        UPDATE notification
        SET is_read = 1
        WHERE id = :notification_id;
        """
        db.session.execute(text(sql_query), {"notification_id": notification_id})
        db.session.commit()

    @staticmethod
    def remove_notification(notification_id):
        """
        Remove a notification from the database.
        """
        sql_query = """
        DELETE FROM notification
        WHERE id = :notification_id;
        """
        db.session.execute(text(sql_query), {"notification_id": notification_id})
        db.session.commit()

    @staticmethod
    def get_unread_notifications(user_id):
        """
        Get all unread notifications for a user.
        """
        sql_query = """
        SELECT n.*, u.username AS assigned_username
        FROM notification n
        LEFT JOIN peoples u ON n.assigned_user_id = u.id
        WHERE n.user_id = :user_id AND n.is_read = 0
        ORDER BY n.timestamp DESC;
        """
        result = db.session.execute(
            text(sql_query),
            {"user_id": user_id}
        )
        return result.fetchall()

    @staticmethod
    def clear_read_notifications(user_id):
        """
        Delete all read notifications for a user.
        """
        sql_query = """
        DELETE FROM notification
        WHERE user_id = :user_id AND is_read = 1;
        """
        db.session.execute(text(sql_query), {"user_id": user_id})
        db.session.commit()
