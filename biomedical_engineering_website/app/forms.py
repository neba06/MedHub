from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateTimeField, TextAreaField, IntegerField, SelectMultipleField, BooleanField, DateField
from wtforms.validators import DataRequired, Optional
from wtforms.validators import DataRequired, Optional, Length
from datetime import datetime
from wtforms.widgets import ListWidget, CheckboxInput

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField(
        'Role', 
        choices=[('admin', 'Admin'), 
                 ('engineer', 'Engineer'), 
                 ('technician', 'Technician'),
                 ('user', 'User')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class DeviceForm(FlaskForm):
    name = StringField('Device Name', validators=[DataRequired(), Length(max=100)])
    model_number = StringField('Model Number', validators=[DataRequired(), Length(max=50)])
    serial_number = StringField('Serial Number', validators=[DataRequired(), Length(max=50)])
    manufacturer = StringField('Manufacturer', validators=[DataRequired(), Length(max=100)])
    purchase_date = DateField('Purchase Date', format='%Y-%m-%d', validators=[DataRequired()])
    warranty_expiry_date = DateField('Warranty Expiry Date', format='%Y-%m-%d', validators=[DataRequired()])
    maintenance_schedule_daily = BooleanField('Daily')
    maintenance_schedule_weekly = BooleanField('Weekly')
    maintenance_schedule_monthly = BooleanField('Monthly')
    maintenance_schedule_quarterly = BooleanField('Quarterly')
    maintenance_schedule_yearly = BooleanField('Yearly')
    maintenance_interval = IntegerField('Maintenance Interval (Days)', validators=[DataRequired()])

    status = SelectField(
        'Status',
        choices=[('Active', 'Active'), ('Inactive', 'Inactive'), ('Decommissioned', 'Decommissioned')],
        validators=[DataRequired()]
    )

    location = StringField('Location', validators=[Length(max=100)])
    health_status = SelectField(
        'Health Status',
        choices=[('Good', 'Good'), ('Fair', 'Fair'), ('Critical', 'Critical')],
        validators=[DataRequired()]
    )

    submit = SubmitField('Submit')


class MaintenanceForm(FlaskForm):
    maintenance_type = SelectField(
        'Maintenance Type',
        choices=[
            ('Daily', 'Daily'),
            ('Weekly', 'Weekly'),
            ('Monthly', 'Monthly'),
            ('Quarterly', 'Quarterly'),
            ('Biannual', 'Biannual'),
            ('Yearly', 'Yearly'),
            ('Other', 'Other'),  # New option for custom maintenance types
        ],
        validators=[DataRequired()]
    )
    custom_maintenance_type = StringField(
        'Custom Maintenance Type (if "Other" selected)',
        validators=[]  # Optional field, validation handled conditionally
    )
    details = TextAreaField('Details', validators=[DataRequired()])
    submit = SubmitField('Add Maintenance Record')

class StockItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    submit = SubmitField('Save Item')

class IncidentReportForm(FlaskForm):
    device_id = SelectField('Device', coerce=int, choices=[], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    resolution_status = StringField('Resolution Status', default='Open')
    submit = SubmitField('Submit Report')

class TaskForm(FlaskForm):
    title = StringField('Task Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    device_id = SelectField('Device', coerce=int, choices=[], validators=[Optional()])
    assigned_to = SelectField('Assign To', coerce=int, choices=[], validators=[DataRequired()])
    priority = SelectField(
        'Priority', 
        choices=[('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')], 
        validators=[DataRequired()]
    )
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Create Task')

class TaskStatusForm(FlaskForm):
    status = SelectField(
        'Status',
        choices=[
            ('Not Started', 'Not Started'),
            ('In Progress', 'In Progress'),
            ('Completed', 'Completed')
        ],
        validators=[DataRequired()]
    )
    completion_details = TextAreaField('Completion Details')  # Optional field for completion details
    submit = SubmitField('Update Status')
class ReminderForm(FlaskForm):
    user_id = SelectField('User', coerce=int, choices=[], validators=[DataRequired()])
    device_id = SelectField('Device', coerce=int, choices=[], validators=[Optional()])
    task_id = SelectField('Task', coerce=int, choices=[], validators=[Optional()])
    message = StringField('Reminder Message', validators=[DataRequired()])
    reminder_time = DateTimeField('Reminder Time', format='%Y-%m-%d %H:%M:%S', validators=[DataRequired()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Reminder')
