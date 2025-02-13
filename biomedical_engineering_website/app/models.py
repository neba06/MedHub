from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.event import listens_for

from sqlalchemy.orm import scoped_session, sessionmaker


db = SQLAlchemy()  # Initialize db here

class User(db.Model, UserMixin):
    __tablename__ = 'peoples'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # Role: 'admin', 'engineer', 'technician', or 'user'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"



class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    model_number = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=False)
    manufacturer = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Active")
    location = db.Column(db.String(200), nullable=True)
    purchase_date = db.Column(db.DateTime, nullable=True)
    warranty_expiry_date = db.Column(db.DateTime, nullable=True)
    maintenance_schedule = db.Column(db.String(200), nullable=False)
    last_maintenance_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    maintenance_interval = db.Column(db.Integer, nullable=False)
    next_maintenance_date = db.Column(db.DateTime, nullable=False)
    health_status = db.Column(db.String(50), nullable=False, default='Good')

    added_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    assigned_at = db.Column(db.DateTime, nullable=True)

    # New field for tracking the user who added the device
    added_by = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)
    added_user = db.relationship('User', backref='added_devices', lazy=True, foreign_keys=[added_by])

    # Foreign key and relationship
    maintenances = db.relationship('Maintenance', backref='device', lazy=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=True)
    assigned_user = db.relationship('User', backref='assigned_devices', lazy=True, primaryjoin="Device.assigned_to == User.id")

    def __repr__(self):
        return f"<Device {self.name}>"



class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    maintenance_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    maintenance_type = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Maintenance {self.maintenance_type} for {self.device.name} on {self.maintenance_date}>"

class StockItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Name of the stock item (e.g., Spare Part)
    quantity = db.Column(db.Integer, nullable=False)  # Available quantity
    description = db.Column(db.String(200), nullable=True)  # Description of the item (e.g., type, usage)
    
    def __repr__(self):
        return f"<StockItem {self.name}>"


class IncidentReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    report_date = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)
    description = db.Column(db.Text, nullable=False)
    resolution_status = db.Column(db.String(50), default='Open')
    assigned_to = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=True)

    # New field for tracking the user who reported the incident
    reported_by = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)
    reporting_user = db.relationship('User', backref='reported_incidents', lazy=True, foreign_keys=[reported_by])

    # Add the relationship to easily access the related device
    device = db.relationship('Device', backref='incidents', lazy=True)
    assigned_user = db.relationship('User', backref='assigned_incidents', lazy=True, primaryjoin="IncidentReport.assigned_to == User.id")

    def __repr__(self):
        return f"<IncidentReport for Device {self.device_id}: {self.description[:20]}>"

class Analytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    metric = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp(), nullable=False)

    def __repr__(self):
        return f"<Analytics for Device {self.device_id}: {self.metric} = {self.value}>"

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)
    show_total_devices = db.Column(db.Boolean, default=True)
    show_total_incidents = db.Column(db.Boolean, default=True)
    show_total_maintenance_tasks = db.Column(db.Boolean, default=True)
    show_upcoming_maintenance = db.Column(db.Boolean, default=True)
    show_recent_incidents = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<UserPreference for User {self.user_id}>"

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=True)  # Optional: Link to a device
    assigned_to = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=True)  # Assigned technician/engineer
    created_by = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)  # Task creator
    priority = db.Column(db.String(20), nullable=False, default="Medium")  # Priority: Critical, High, Medium, Low
    status = db.Column(db.String(50), nullable=False, default="Not Started")  # Task status
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    device = db.relationship('Device', backref='tasks', lazy=True)
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], backref='tasks_assigned', lazy=True)
    creator_user = db.relationship('User', foreign_keys=[created_by], backref='tasks_created', lazy=True)

    def __repr__(self):
        return f"<Task {self.title} assigned to {self.assigned_to}>"


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)  # User who gets the reminder
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=True)  # Device associated with the reminder
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)  # Task related to the reminder
    message = db.Column(db.String(255), nullable=False)  # Reminder message
    reminder_time = db.Column(db.DateTime, nullable=False)  # Time when the reminder should trigger
    is_active = db.Column(db.Boolean, default=True)  # Whether the reminder is active or not
    is_sent = db.Column(db.Boolean, default=False)  # Whether the reminder has been sent

    user = db.relationship('User', backref='reminders', lazy=True)
    device = db.relationship('Device', backref='reminders', lazy=True)
    task = db.relationship('Task', backref='reminders', lazy=True)

    def __repr__(self):
        return f"<Reminder for {self.user.username}: {self.message} at {self.reminder_time}>"

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=True)  # New field to track related device

    # Relationships
    user = db.relationship('User', backref='activity_logs', lazy=True)
    device = db.relationship('Device', backref='activity_logs', lazy=True)

    def __repr__(self):
        return f"<ActivityLog User {self.user_id}: {self.action}>"


class Notification(db.Model):
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incident_report.id'), nullable=True)  # Added for incidents
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('peoples.id'), nullable=True)
    
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_read = db.Column(db.Boolean, default=False)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications', lazy=True)
    device = db.relationship('Device', backref='notifications', lazy=True)
    task = db.relationship('Task', backref='notifications', lazy=True)
    incident = db.relationship('IncidentReport', backref='notifications', lazy=True)  # Added relationship for incidents
    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id], backref='assigned_notifications', lazy=True)

    def __repr__(self):
        return f"<Notification(type={self.type}, user_id={self.user_id}, assigned_user_id={self.assigned_user_id})>"
