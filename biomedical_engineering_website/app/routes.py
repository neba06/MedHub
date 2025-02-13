from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from .forms import LoginForm, TaskForm, ReminderForm, TaskStatusForm, StockItemForm, RegistrationForm, IncidentReportForm, DeviceForm, MaintenanceForm
from .models import Task, Notification, User, ActivityLog, StockItem, Reminder, IncidentReport, UserPreference, Analytics, Device, Maintenance 
from . import db
from flask_login import login_required, current_user, login_user, logout_user
from datetime import datetime, timedelta, date 
from flask import render_template, flash, redirect, url_for
from sqlalchemy import DateTime
from sqlalchemy.sql import text, func
from sqlalchemy.orm import joinedload
from .utilities import log_activity, NotificationManager, create_maintenance_tasks


bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def index():
    """Homepage showing notifications and categorized schedules."""
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Fetch tasks for today and this week
    todays_tasks = Task.query.filter(Task.due_date == today, Task.status != 'Completed').order_by(Task.due_date).all()
    this_weeks_tasks = Task.query.filter(
        Task.due_date >= start_of_week, Task.due_date <= end_of_week, Task.status != 'Completed'
    ).order_by(Task.due_date).all()
    devices = Device.query.filter(Device.assigned_to == current_user.id).all()
    for device in devices:
        
        device.next_maintenance_date = device.last_maintenance_date + timedelta(days=device.maintenance_interval)
        db.session.commit()
    overdue_maintenance = [
    device for device in devices if device.next_maintenance_date < datetime.utcnow()
]



    if current_user.role == 'admin':
        # Admin sees only their own notifications
        notifications = db.session.query(
            Notification,
            User.username.label('assigned_username')
        ).outerjoin(User, Notification.assigned_user_id == User.id) \
         .filter(Notification.user_id == current_user.id) \
         .order_by(Notification.timestamp.desc()) \
         .all()
    else:
        # Non-admin users also receive results as rows with Notification and assigned_username
        notifications = db.session.query(
            Notification,
            User.username.label('assigned_username')
        ).outerjoin(User, Notification.assigned_user_id == User.id) \
         .filter(Notification.user_id == current_user.id) \
         .order_by(Notification.timestamp.desc()) \
         .all()

    # Recent items
    if current_user.role == 'admin':
        recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
        recent_incidents = IncidentReport.query.order_by(IncidentReport.report_date.desc()).limit(5).all()
        recent_devices = Device.query.order_by(Device.updated_at.desc()).limit(5).all()
    elif current_user.role == 'user':
        recent_tasks = []
        recent_incidents = IncidentReport.query.filter_by(assigned_to=current_user.id).order_by(IncidentReport.report_date.desc()).limit(5).all()
        recent_devices = []
    else:
        recent_tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.created_at.desc()).limit(5).all()
        recent_incidents = IncidentReport.query.filter_by(assigned_to=current_user.id).order_by(IncidentReport.report_date.desc()).limit(5).all()
        recent_devices = Device.query.filter_by(assigned_to=current_user.id).order_by(Device.updated_at.desc()).limit(5).all()

    # Warranty Expiry for Admins
    warranty_expiry = []
    if current_user.role == 'admin':
        current_month_start = today.replace(day=1)  # Start of the current month
        next_month_start = (current_month_start + timedelta(days=31)).replace(day=1)  # Start of next month
        warranty_expiry = Device.query.filter(
            Device.warranty_expiry_date >= current_month_start,
            Device.warranty_expiry_date < next_month_start
        ).order_by(Device.warranty_expiry_date).all()

    if current_user.role == 'admin':
        # Admin sees all tasks and devices
        user_tasks = Task.query.order_by(Task.due_date).all()
        user_devices = Device.query.order_by(Device.next_maintenance_date).all()
    else:
        # Regular users see their tasks and assigned devices
        user_tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date).all()
        user_devices = Device.query.filter_by(assigned_to=current_user.id).order_by(Device.next_maintenance_date).all()
    
    return render_template(
        'index.html',
        notifications=notifications,
        todays_tasks=todays_tasks,
        this_weeks_tasks=this_weeks_tasks,
        warranty_expiry=warranty_expiry,
        recent_tasks=recent_tasks,
        recent_incidents=recent_incidents,
        recent_devices=recent_devices,
        devices=devices,
        overdue_maintenance=overdue_maintenance,
        user_tasks=user_tasks,
        user_devices=user_devices,
    )



@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)  # Use Flask-Login's login_user method
            session['role'] = user.role  # Store role in session
            flash(f'Login successful! Role: {user.role}', 'success')
            log_activity(user.id, 'Logged in')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

# Route for registering new users
@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('main.register'))

        new_user = User(
            username=username,
            password=generate_password_hash(password),
            role=role
        )
        db.session.add(new_user)
        db.session.commit()
        log_activity(new_user.id, 'Registered a new account')
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@bp.route('/devices', methods=['GET'])
@login_required
def devices():
    # Log user activity
    log_activity(current_user.id, 'Viewed devices')

    # Get filters from the request
    search_query = request.args.get('search')
    unassigned_devices = []
    status_filter = request.args.get('status')
    location_filter = request.args.get('location')
    health_status_filter = request.args.get('health_status')
    manufacturer_filter = request.args.get('manufacturer')

    # Base query
    query = Device.query

    # Apply filters
    if search_query:
        query = query.filter(Device.name.ilike(f"%{search_query}%") |
                             Device.model_number.ilike(f"%{search_query}%") |
                             Device.serial_number.ilike(f"%{search_query}%"))

    if status_filter:
        query = query.filter(Device.status == status_filter)

    if location_filter:
        query = query.filter(Device.location == location_filter)

    if health_status_filter:
        query = query.filter(Device.health_status == health_status_filter)

    if manufacturer_filter:
        query = query.filter(Device.manufacturer == manufacturer_filter)

    # Role-based visibility
    if current_user.role == 'technician':
        # Show only devices assigned to the current user
        query = query.filter(Device.assigned_to == current_user.id)
    elif current_user.role == 'engineer':
        # Show devices assigned to the user and all devices
        devices = query.all()
        your_devices = [d for d in devices if d.assigned_to == current_user.id]
        return render_template('devices.html', devices=devices, your_devices=your_devices)

    # For admin, show all devices
    devices = query.all()
    unassigned_devices = [device for device in devices if device.assigned_to is None]
    return render_template('devices.html', devices=devices, unassigned_devices=unassigned_devices)



@bp.route('/device/add', methods=['GET', 'POST']) 
@login_required
def add_device():
    form = DeviceForm()

    if form.validate_on_submit():
         # Check for duplicate serial numbers
        existing_device = Device.query.filter_by(serial_number=form.serial_number.data).first()
        if existing_device:
            flash('A device with this serial number already exists.', 'danger')
            return render_template('add_device.html', form=form)
        maintenance_schedule = []
        if form.maintenance_schedule_daily.data:
            maintenance_schedule.append('Daily')
        if form.maintenance_schedule_weekly.data:
            maintenance_schedule.append('Weekly')
        if form.maintenance_schedule_monthly.data:
            maintenance_schedule.append('Monthly')
        if form.maintenance_schedule_quarterly.data:
            maintenance_schedule.append('Quarterly')
        if form.maintenance_schedule_yearly.data:
            maintenance_schedule.append('Yearly')
        maintenance_schedule = ', '.join(maintenance_schedule)

        purchase_date = datetime.combine(form.purchase_date.data, datetime.min.time())
        warranty_expiry_date = datetime.combine(form.warranty_expiry_date.data, datetime.min.time())

        sql_query = text("""
        INSERT INTO Device 
        (name, model_number, serial_number, manufacturer, status, location, purchase_date, warranty_expiry_date, 
        maintenance_schedule, last_maintenance_date, maintenance_interval, next_maintenance_date, added_by) 
        VALUES (:name, :model_number, :serial_number, :manufacturer, :status, :location, :purchase_date, 
        :warranty_expiry_date, :maintenance_schedule, :last_maintenance_date, :maintenance_interval, 
        :next_maintenance_date, :added_by);
        """)
        values = {
            'name': form.name.data,
            'model_number': form.model_number.data,
            'serial_number': form.serial_number.data,
            'manufacturer': form.manufacturer.data,
            'status': form.status.data,
            'location': form.location.data,
            'purchase_date': purchase_date,
            'warranty_expiry_date': warranty_expiry_date,
            'maintenance_schedule': maintenance_schedule,
            'last_maintenance_date': datetime.utcnow(),
            'maintenance_interval': form.maintenance_interval.data,
            'next_maintenance_date': datetime.utcnow() + timedelta(days=form.maintenance_interval.data),
            'added_by': current_user.id
        }

        db.session.execute(sql_query, values)
        db.session.commit()

        # Retrieve the newly created device
        device = Device.query.filter_by(serial_number=form.serial_number.data).first()

        if device:
            # Pass both the device and current_user to create_maintenance_tasks
            create_maintenance_tasks(device=device, current_user=current_user)

            # Notify admins when a new device is added
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                message = f"A new device '{form.name.data}' was added by {current_user.username}."
                NotificationManager.add_notification(
                    user_id=admin.id,  # Send notification to each admin
                    message=message,
                    notif_type='Device',
                    device_id=device.id
            )

        log_activity(current_user.id, f'Added device: {device.name}', device=device)
        flash('Device and maintenance tasks added successfully!', 'success')
        return redirect(url_for('main.devices'))

    return render_template('add_device.html', form=form)




@bp.route('/device/<int:id>', methods=['GET'])
@login_required
def device_details(id):
    device = Device.query.get_or_404(id)
    users = User.query.filter(User.role.in_(['technician', 'engineer'])).all()
    
    # Calculate upcoming maintenance dates
    upcoming_maintenance_dates = []
    maintenance_date = device.next_maintenance_date
    
    # Generate the next 12 maintenance dates based on the maintenance interval
    for _ in range(12):
        upcoming_maintenance_dates.append(maintenance_date)
        maintenance_date += timedelta(days=device.maintenance_interval)
    
    return render_template('device_details.html', device=device, users=users, upcoming_maintenance_dates=upcoming_maintenance_dates)
@bp.route('/device/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_device(id):
    device = Device.query.get_or_404(id)
    form = DeviceForm(obj=device)  # Populate the form with the current device data
    if form.validate_on_submit():
        # Update the device attributes based on the form data
        device.name = form.name.data
        device.model_number = form.model_number.data
        device.serial_number = form.serial_number.data
        device.manufacturer = form.manufacturer.data
        device.location = form.location.data

        # Convert dates to datetime objects (if needed)
        # If you're using DateField, it will be a datetime.date object, but you need a datetime.datetime object
        device.purchase_date = datetime.combine(form.purchase_date.data, datetime.min.time())
        device.warranty_expiry_date = datetime.combine(form.warranty_expiry_date.data, datetime.min.time())

        # Construct the maintenance schedule from the selected boolean fields
        maintenance_schedule = []
        if form.maintenance_schedule_daily.data:
            maintenance_schedule.append('Daily')
        if form.maintenance_schedule_weekly.data:
            maintenance_schedule.append('Weekly')
        if form.maintenance_schedule_monthly.data:
            maintenance_schedule.append('Monthly')
        if form.maintenance_schedule_quarterly.data:
            maintenance_schedule.append('Quarterly')
        if form.maintenance_schedule_yearly.data:
            maintenance_schedule.append('Yearly')

        # Join the selected maintenance schedule types with commas
        device.maintenance_schedule = ', '.join(maintenance_schedule)

        device.maintenance_interval = form.maintenance_interval.data
        db.session.commit()  # Save the changes to the database
        # Log the activity
        log_activity(current_user.id, f'Updated device: {device.name}', device=device)
        flash('Device updated successfully!', 'success')  # Show success message
        return redirect(url_for('main.device_details', id=device.id))  # Redirect to the device details page
    
    return render_template('edit_device.html', form=form, device=device)  # Render the form for editing

@bp.route('/assign_device', methods=['GET', 'POST'])
@login_required
def assign_device():
    """Route to assign a device to a technician or engineer."""
    if current_user.role != 'admin':
        flash('Access Denied. Admins only.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Get unassigned devices and eligible users (technicians and engineers)
    devices = Device.query.filter_by(assigned_to=None).all()
    technicians_and_engineers = User.query.filter(User.role.in_(['technician', 'engineer'])).all()

    if request.method == 'POST':
        # Process form data
        device_id = request.form.get('device_id')
        assignee_id = request.form.get('assignee_id')

        device = Device.query.get(device_id)
        assignee = User.query.get(assignee_id)

        if device and assignee:
            # Assign device
            device.assigned_to = assignee.id
            device.assigned_at = datetime.utcnow()
            db.session.commit()

            # Notify the assigned user
            NotificationManager.add_notification(
                user_id=assignee.id,
                message=f"You have been assigned a new device: {device.name}",
                notif_type="Device Assignment",
                device_id=device.id,
                assigned_user_id=assignee.id
            )

            # Log activity
            log_activity(current_user.id, f'Assigned device "{device.name}" to {assignee.username}', device=device)
            flash(f'Device "{device.name}" successfully assigned to {assignee.username}!', 'success')
            return redirect(url_for('main.assign_device'))

        flash('Error assigning device. Please try again.', 'danger')

    return render_template('assign_device.html', devices=devices, technicians_and_engineers=technicians_and_engineers)


@bp.route('/device/<int:id>/update_status', methods=['POST'])
@login_required
def update_device_status(id):
    """Route to update the status and health status of a device."""
    device = Device.query.get_or_404(id)

    # Ensure user is authorized to update status
    if device.assigned_to != current_user.id:
        flash('Access Denied. You do not have permission to update this device.', 'danger')
        return redirect(url_for('main.device_details', id=id))

    # Get status updates from the form
    new_status = request.form.get('status')
    new_health_status = request.form.get('health_status')

    if new_status or new_health_status:
        if new_status:
            device.status = new_status
        if new_health_status:
            device.health_status = new_health_status

        device.updated_at = datetime.utcnow()
        db.session.commit()

        # Log activity
        log_activity(current_user.id, f"Updated status of device '{device.name}'", device=device)

        # Notify admins about the update
        message = f"The status or health status of the device '{device.name}' was updated by {current_user.username}."
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            NotificationManager.add_notification(
                user_id=admin.id,
                message=message,
                notif_type='Device',
                device_id=device.id
            )

        flash('Device status updated successfully!', 'success')
    else:
        flash('No changes detected. Please update at least one field.', 'warning')

    return redirect(url_for('main.device_details', id=id))

@bp.route('/device/<int:id>/delete', methods=['POST'])
@login_required
def delete_device(id):
    # Check if the logged-in user has the 'admin' role
    if current_user.role != 'admin':
        abort(403)  # HTTP 403 Forbidden

    # Fetch the device to be deleted
    device = Device.query.get_or_404(id)

    # Log the deletion activity before deleting the device
    log_activity(current_user.id, f'Deleted device: {device.name}', device=device)

    # Delete related incident reports
    related_incidents = IncidentReport.query.filter_by(device_id=device.id).all()
    for incident in related_incidents:
        db.session.delete(incident)

    # Delete the device
    db.session.delete(device)
    db.session.commit()

    # Show success message and redirect
    flash('Device and related incidents deleted successfully!', 'success')
    return redirect(url_for('main.devices'))



# Route to display all stock items
@bp.route('/stock', methods=['GET'])
@login_required
def view_stock():
    stock_items = StockItem.query.all()  # Fetch all stock items
    low_stock_items = StockItem.query.filter(StockItem.quantity < 10).all()  # Items with low stock (<10)
    log_activity(current_user.id, 'Viewed stock items')
    return render_template('stock.html', stock_items=stock_items, low_stock_items=low_stock_items)
@bp.route('/stock/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_stock(id):
    stock_item = StockItem.query.get_or_404(id)
    form = StockItemForm(obj=stock_item)  # Prepopulate form with existing data
    if form.validate_on_submit():
        stock_item.name = form.name.data
        stock_item.quantity = form.quantity.data
        stock_item.description = form.description.data
        db.session.commit()
        log_activity(current_user.id, f"Edited stock item: {stock_item.name}")
        flash('Stock item updated successfully!', 'success')
        return redirect(url_for('main.view_stock'))
    return render_template('edit_stock.html', form=form, item=stock_item)

# Route to add a new stock item
@bp.route('/stock/add', methods=['GET', 'POST'])
@login_required
def add_stock():
    form = StockItemForm()
    if form.validate_on_submit():
        # Create a new stock item from the form data
        new_item = StockItem(
            name=form.name.data,
            quantity=form.quantity.data,
            description=form.description.data
        )
        db.session.add(new_item)
        db.session.commit()
        log_activity(current_user.id, "Added stock item")  # Log the activity
        flash('Stock item added successfully!', 'success')
        return redirect(url_for('main.view_stock'))  # Redirect to the stock page after adding
    return render_template('add_stock.html', form=form)

# Route to delete a stock item
@bp.route('/stock/delete/<int:id>', methods=['POST'])
@login_required
def delete_stock(id):
    stock_item = StockItem.query.get_or_404(id)
    db.session.delete(stock_item)
    db.session.commit()
    log_activity(current_user.id, "Deleted stock item")  # Log the activity
    flash('Stock item deleted successfully!', 'success')
    return redirect(url_for('main.view_stock'))



@bp.route('/analytics')
def analytics():
    # Devices
    total_devices = Device.query.count()
    active_devices = Device.query.filter_by(status='Active').count()
    healthy_devices = Device.query.filter_by(health_status='Good').count()
    fair_devices = Device.query.filter_by(health_status='Fair').count()
    critical_devices = Device.query.filter_by(health_status='Critical').count()

    # Incidents
    total_incidents = IncidentReport.query.count()
    resolved_incidents = IncidentReport.query.filter_by(resolution_status='Resolved').count()
    open_incidents = total_incidents - resolved_incidents

    # Tasks
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='Completed').count()
    in_progress_tasks = Task.query.filter_by(status='In Progress').count()
    not_started_tasks = Task.query.filter(Task.status.in_(['Not Started', 'Pending'])).count()
    critical_tasks = Task.query.filter_by(priority='Critical').count()
    high_tasks = Task.query.filter_by(priority='High').count()
    medium_tasks = Task.query.filter_by(priority='Medium').count()
    low_tasks = Task.query.filter_by(priority='Low').count()

    # Stock Items
    total_stock_items = StockItem.query.count()

    # Users
    total_users = User.query.count()
    engineers = User.query.filter_by(role='Engineer').count()
    technicians = User.query.filter_by(role='Technician').count()

    # Maintenance
    total_maintenance_tasks = Maintenance.query.count()
    daily_maintenance = Device.query.filter_by(maintenance_schedule='Daily').count()
    weekly_maintenance = Device.query.filter_by(maintenance_schedule='Weekly').count()
    monthly_maintenance = Device.query.filter_by(maintenance_schedule='Monthly').count()
    quarterly_maintenance = Device.query.filter_by(maintenance_schedule='Quarterly').count()
    yearly_maintenance = Device.query.filter_by(maintenance_schedule='Yearly').count()

    # Activity Log
    login_activities = ActivityLog.query.filter(ActivityLog.action.like('%logged in%')).count()
    update_activities = ActivityLog.query.filter(ActivityLog.action.like('%updated%')).count()
    report_activities = ActivityLog.query.filter(ActivityLog.action.like('%reported%')).count()

    # User Activities
    most_active_users = (
    User.query.join(ActivityLog)
    .with_entities(
        User.id,
        User.username,
        User.password,
        User.role,
        User.joined_at,
        func.count(ActivityLog.id).label('activity_count')
    )
    .group_by(User.id, User.username, User.password, User.role, User.joined_at)
    .order_by(func.count(ActivityLog.id).desc())
    .limit(5)
    .all()
)

    most_active_user_names = [user.username for user in most_active_users]
    most_active_user_counts = [user.activity_count for user in most_active_users]


    # Website Activity Trends
    from sqlalchemy import cast, Date

    website_activity_data = (
        ActivityLog.query.filter(ActivityLog.action.like('%logged in%'))
        .with_entities(
            cast(ActivityLog.timestamp, Date).label('date'),
            func.count().label('count')
    )
        .group_by(cast(ActivityLog.timestamp, Date))
        .order_by(cast(ActivityLog.timestamp, Date))
        .all()
)

    website_activity_dates = [record.date.strftime('%Y-%m-%d') for record in website_activity_data]
    website_activity_counts = [record.count for record in website_activity_data]
    assigned_tasks = Task.query.filter(Task.assigned_to.isnot(None)).count()
    unassigned_tasks = total_tasks - assigned_tasks

    assigned_incidents = IncidentReport.query.filter(IncidentReport.assigned_to.isnot(None)).count()
    unassigned_incidents = total_incidents - assigned_incidents

    assigned_devices = Device.query.filter(Device.assigned_to.isnot(None)).count()
    unassigned_devices = total_devices - assigned_devices
    # Calculations
    healthy_devices_percentage = round((healthy_devices / total_devices) * 100, 1) if total_devices else 0
    fair_devices_percentage = round((fair_devices / total_devices) * 100, 1) if total_devices else 0
    critical_devices_percentage = round((critical_devices / total_devices) * 100, 1) if total_devices else 0
    resolved_incidents_percentage = round((resolved_incidents / total_incidents) * 100, 1) if total_incidents else 0
    open_incidents_percentage = round(100 - resolved_incidents_percentage, 1) if total_incidents else 0
    completed_tasks_percentage = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0
    in_progress_tasks_percentage = round((in_progress_tasks / total_tasks) * 100, 1) if total_tasks else 0
    not_started_tasks_percentage = round((not_started_tasks / total_tasks) * 100, 1) if total_tasks else 0

    # Log Activity
    log_activity(current_user, 'Accessed Analytics')

    return render_template(
        'analytics.html',
        total_devices=total_devices,
        active_devices=active_devices,
        total_incidents=total_incidents,
        open_incidents_percentage=open_incidents_percentage,
        resolved_incidents_percentage=resolved_incidents_percentage,
        healthy_devices_percentage=healthy_devices_percentage,
        fair_devices_percentage=fair_devices_percentage,
        critical_devices_percentage=critical_devices_percentage,
        critical_tasks=critical_tasks,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        not_started_tasks=not_started_tasks,
        completed_tasks_percentage=completed_tasks_percentage,
        in_progress_tasks_percentage=in_progress_tasks_percentage,
        not_started_tasks_percentage=not_started_tasks_percentage,
        high_tasks=high_tasks,
        medium_tasks=medium_tasks,
        low_tasks=low_tasks,
        total_users=total_users,
        engineers=engineers,
        technicians=technicians,
        login_activities=login_activities,
        update_activities=update_activities,
        total_stock_items=total_stock_items,
        total_maintenance_tasks=total_maintenance_tasks, 
        daily_maintenance=daily_maintenance, 
        weekly_maintenance=weekly_maintenance, 
        monthly_maintenance=monthly_maintenance, 
        quarterly_maintenance=quarterly_maintenance, 
        yearly_maintenance=yearly_maintenance, 
        report_activities=report_activities,
        most_active_user_names=most_active_user_names,
        most_active_user_counts=most_active_user_counts,
        website_activity_dates=website_activity_dates,
        website_activity_counts=website_activity_counts,
        assigned_tasks=assigned_tasks,
        unassigned_tasks=unassigned_tasks,
        assigned_incidents=assigned_incidents,
        unassigned_incidents=unassigned_incidents,
        assigned_devices=assigned_devices,
        unassigned_devices=unassigned_devices,
    )


@bp.route('/dashboard')
@login_required
def dashboard():
    # Fetch relevant data
    total_devices = Device.query.count()
    total_incidents = IncidentReport.query.count()
    total_tasks = Task.query.count()
    total_maintenance_tasks = Maintenance.query.count()

    # Devices with upcoming maintenance
    upcoming_maintenance_devices = Device.query.filter(Device.next_maintenance_date > datetime.now()).limit(5).all()
    upcoming_maintenance_count = len(upcoming_maintenance_devices)

    # Recent tasks assigned to the engineer
    recent_tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.created_at.desc()).limit(5).all()


    # Fetch the device counts based on status
    device_health = Device.query.filter_by(health_status='Critical').all()
    device_health_count = Device.query.filter_by(health_status='Critical').count()
    device_status_count = Device.query.filter_by(status='Inactive').count()
    low_stock_count = StockItem.query.filter(StockItem.quantity < 10).count()

    # Fetch unassigned items
    unassigned_devices = Device.query.filter(Device.assigned_to.is_(None)).count()
    unassigned_device_list = Device.query.filter(Device.assigned_to.is_(None)).all()

    unassigned_tasks = total_tasks - Task.query.filter(Task.assigned_to.isnot(None)).count()
    unassigned_task_list = Task.query.filter(Task.assigned_to.is_(None)).all()

    unassigned_incidents = total_incidents - IncidentReport.query.filter(IncidentReport.assigned_to.isnot(None)).count()
    unassigned_incident_list = IncidentReport.query.filter(IncidentReport.assigned_to.is_(None)).all()
    
    # Fetch inactive devices and low stock items
    inactive_devices = Device.query.filter(Device.status == 'Inactive').all()
    low_stock_items = StockItem.query.filter(StockItem.quantity < 10).all()

    # Count of recent updates or logs
    recent_updates_count = ActivityLog.query.filter(ActivityLog.timestamp > datetime.now() - timedelta(days=7)).count()


    # Fetch incidents based on user role
    if current_user.role == 'admin':
        incidents = IncidentReport.query.all()  # Admin can see all incidents
        log_activity(current_user, 'Accessed admin dashboard')  # Log the activity

        return render_template(
            'admin_dashboard.html',
            total_devices=total_devices,
            total_incidents=total_incidents,
            total_maintenance_tasks=total_maintenance_tasks,
            incidents=incidents,
            device_health=device_health,
            inactive_devices=inactive_devices,
            low_stock_items=low_stock_items,
            recent_updates_count=recent_updates_count,
            unassigned_devices=unassigned_devices,
            unassigned_device_list=unassigned_device_list,
            unassigned_tasks=unassigned_tasks,
            unassigned_task_list=unassigned_task_list,
            unassigned_incidents=unassigned_incidents,
            unassigned_incident_list=unassigned_incident_list,
            device_health_count=device_health_count,
            device_status_count=device_status_count,
            low_stock_count=low_stock_count,

        )

    elif current_user.role == 'engineer':
        # Assigned devices
        assigned_devices = Device.query.filter_by(assigned_to=current_user.id).all()

        # Assigned tasks
        assigned_tasks = Task.query.filter_by(assigned_to=current_user.id).all()

        # Assigned incidents
        assigned_incidents = IncidentReport.query.filter_by(assigned_to=current_user.id).all()
        devices_added_by_user = Device.query.filter_by(added_by=current_user.id).all()

        # Active reminders
        active_reminders = Reminder.query.filter_by(user_id=current_user.id, is_active=True).all()
        incidents_reported_by_user = IncidentReport.query.filter_by(reported_by=current_user.id).all()


        # Recent notifications
        recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).limit(5).all()
        recent_activity_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.timestamp.desc()).limit(5).all()

        log_activity(current_user, 'Accessed technician dashboard')
        return render_template(
            'engineer_dashboard.html',
            assigned_devices=assigned_devices,
            assigned_tasks=assigned_tasks,
            assigned_incidents=assigned_incidents,
            active_reminders=active_reminders,
            recent_notifications=recent_notifications,
            recent_activity_logs=recent_activity_logs,
            devices_added_by_user=devices_added_by_user,
            incidents_reported_by_user=incidents_reported_by_user,
        )

    elif current_user.role == 'technician':
        # Assigned devices
        assigned_devices = Device.query.filter_by(assigned_to=current_user.id).all()

        # Assigned tasks
        assigned_tasks = Task.query.filter_by(assigned_to=current_user.id).all()

        # Assigned incidents
        assigned_incidents = IncidentReport.query.filter_by(assigned_to=current_user.id).all()

        # Active reminders
        active_reminders = Reminder.query.filter_by(user_id=current_user.id, is_active=True).all()

        # Recent notifications
        recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).limit(5).all()
        recent_activity_logs = ActivityLog.query.filter_by(user_id=current_user.id).order_by(ActivityLog.timestamp.desc()).limit(5).all()

        log_activity(current_user, 'Accessed technician dashboard')
        return render_template(
            'technician_dashboard.html',
            assigned_devices=assigned_devices,
            assigned_tasks=assigned_tasks,
            assigned_incidents=assigned_incidents,
            active_reminders=active_reminders,
            recent_notifications=recent_notifications,
            recent_activity_logs=recent_activity_logs,
        )

    log_activity(current_user, 'Accessed default dashboard')  # Log the activity
    return render_template(
        'default_dashboard.html',
        total_devices=total_devices,
        total_incidents=total_incidents,
        total_maintenance_tasks=total_maintenance_tasks,
        upcoming_maintenance_count=0  # Default value for default dashboard
    )


@bp.route('/device/<int:id>/maintenance', methods=['GET', 'POST'])
@login_required
def maintenance(id):
    """Handle maintenance for a device."""
    # Fetch device or return 404 if not found
    device = Device.query.get_or_404(id)

    # Check if the current user has permission to add maintenance
    if not (device.assigned_to == current_user.id or 
            Task.query.filter_by(device_id=device.id, assigned_to=current_user.id).first()):
        flash("You are not authorized to add maintenance records for this device.", "danger")
        return redirect(url_for('main.devices'))

    form = MaintenanceForm()

    if form.validate_on_submit():
        # Determine maintenance type
        maintenance_type = form.custom_maintenance_type.data if form.maintenance_type.data == "Other" else form.maintenance_type.data

        # Create and save new maintenance record
        maintenance_record = Maintenance(
            device_id=device.id,
            maintenance_type=maintenance_type,
            details=form.details.data,
        )
        db.session.add(maintenance_record)
        db.session.commit()

        # Only update dates and create tasks if the maintenance type is scheduled (daily, weekly, monthly, quarterly, or yearly)
        if maintenance_type in ['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Yearly']:
            # Update the device's last and next maintenance dates
            device.last_maintenance_date = maintenance_record.maintenance_date  # Assuming form includes a maintenance_date field
            if device.maintenance_interval:  # Check if maintenance interval is set
                device.next_maintenance_date = device.last_maintenance_date + timedelta(days=device.maintenance_interval)

            # Create a task for the next maintenance date
            task_due_date = device.next_maintenance_date

            # Create a new maintenance task for the assigned user (current user)
            maintenance_task = Task(
                title=f"Maintenance for {device.name} - {maintenance_type}",
                description=f"Scheduled maintenance for {device.name} ({maintenance_type})",
                device_id=device.id,
                assigned_to=current_user.id,  # Assign the task to the current user
                created_by=current_user.id,  # The user who created the task
                priority="Medium",  # Set a default priority (can be customized)
                status="Not Started",  # Set the default status
                due_date=task_due_date,  # Set the due date for the task
            )
            db.session.add(maintenance_task)
            db.session.commit()

            db.session.commit()  # Commit changes to device and task

        # Log activity and notify admins
        log_activity(current_user.id, f"Added maintenance record for {device.name}", device=device)
        message = f"New maintenance record added for device '{device.name}' by {current_user.username}."
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            NotificationManager.add_notification(admin.id, message, notif_type="Maintenance", device_id=device.id)

        flash("Maintenance record added successfully!", "success")
        return redirect(url_for('main.maintenance', id=device.id))

    return render_template('maintenance.html', form=form, device=device)


@bp.route('/create_incident', methods=['GET', 'POST'])
@login_required
def create_incident():
    # Allow both "engineer" and "user" roles to create incidents
    if current_user.role not in ['engineer', 'user']:
        flash('You are not authorized to view this page.', 'danger')
        return redirect(url_for('main.index'))

    form = IncidentReportForm()

    # Populate the device choices for the select field
    form.device_id.choices = [(device.id, device.name) for device in Device.query.all()]

    if form.validate_on_submit():
        # Create the incident report using SQLAlchemy ORM
        new_incident = IncidentReport(
            device_id=form.device_id.data,
            description=form.description.data,
            resolution_status=form.resolution_status.data,
            report_date=datetime.utcnow(),
            reported_by=current_user.id  # Associate the current user as the reporter
        )

        db.session.add(new_incident)
        db.session.commit()

        # Fetch the device object for logging
        device = Device.query.get(form.device_id.data)

        # Log the activity
        log_activity(current_user.id, f'Reported incident for device: {device.name}', device=device)

        # Notify admins if the reporter is not an engineer
        if current_user.role != 'engineer':
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                message = f"A new incident has been reported for device: {device.name} by {current_user.username}."
                NotificationManager.add_notification(
                    user_id=admin.id,  # Send notification to each admin
                    message=message,
                    notif_type='Incident',
                    incident_id=new_incident.id
                )

        flash('Incident created successfully!', 'success')
        return redirect(url_for('main.view_incidents'))  # Redirect to the dashboard or a specific page

    return render_template('create_incident.html', form=form)


@bp.route('/incidents', methods=['GET'])
@login_required
def view_incidents():
    unassigned_incidents = []
    open_incidents = []
    resolved_incidents = []
    assigned_incidents = []
    reported_incidents = []

    if current_user.role == 'admin':
        unassigned_incidents = IncidentReport.query.filter(IncidentReport.assigned_to == None).all()
        open_incidents = IncidentReport.query.filter(IncidentReport.resolution_status == 'Open').all()
        resolved_incidents = IncidentReport.query.filter(IncidentReport.resolution_status == 'Resolved').all()

    elif current_user.role in ['technician', 'engineer']:
        assigned_incidents = IncidentReport.query.filter_by(assigned_to=current_user.id).all()
        open_incidents = IncidentReport.query.filter(
            IncidentReport.assigned_to == current_user.id,
            IncidentReport.resolution_status == 'Open'
        ).all()
        resolved_incidents = IncidentReport.query.filter(
            IncidentReport.assigned_to == current_user.id,
            IncidentReport.resolution_status == 'Resolved'
        ).all()

    elif current_user.role == 'user':
        reported_incidents = IncidentReport.query.filter_by(reported_by=current_user.id).all()

    return render_template(
        'incidents.html',
        unassigned_incidents=unassigned_incidents if current_user.role == 'admin' else None,
        open_incidents=open_incidents,
        resolved_incidents=resolved_incidents,
        assigned_incidents=assigned_incidents,
        reported_incidents=reported_incidents
    )



@bp.route('/incident/<int:incident_id>', methods=['GET'])
@login_required
def view_incident(incident_id):
    """View details of a specific incident report."""
    incident = IncidentReport.query.get_or_404(incident_id)
    users = User.query.filter(User.role.in_(['engineer', 'technician', 'user'])).all()  # Only engineers/technicians
    log_activity(current_user.id, "Viewed incident")  # Log the activity
    return render_template('view_incident.html', incident=incident, users=users)

@bp.route('/incident/<int:incident_id>/update', methods=['POST'])
@login_required
def update_incident(incident_id):
    """Update the resolution status of an incident."""
    incident = IncidentReport.query.get_or_404(incident_id)
    
    # Check if the current user is authorized to update
    if current_user.id != incident.assigned_to and current_user.role != 'admin':
        flash('You are not authorized to update this incident.', 'danger')
        return redirect(url_for('main.view_incident', incident_id=incident_id))
    
    resolution_status = request.form.get('resolution_status')
    incident.resolution_status = resolution_status
    db.session.commit()
    log_activity(current_user.id, "Updated incident")
    if incident.resolution_status == 'Resolved' or 'Closed':
        message = f"The incident for device: {incident.device.name} has been resolved by: { current_user.username }."
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            NotificationManager.add_notification(
                user_id=admin.id,  # Send notification to each admin
                message=message,
                notif_type='Incident',
                incident_id=incident.id
            )
    flash('Incident status updated successfully.', 'success')
    return redirect(url_for('main.view_incident', incident_id=incident_id))

@bp.route('/incident/<int:incident_id>/assign', methods=['POST'])
@login_required
def assign_incident(incident_id):
    if current_user.role != 'admin':
        flash('You are not authorized to assign incidents.', 'danger')
        return redirect(url_for('main.view_incident', incident_id=incident_id))

    incident = IncidentReport.query.get_or_404(incident_id)
    assigned_to = request.form.get('assigned_to')

    user = User.query.filter_by(id=assigned_to).first()
    if not user or user.role not in ['engineer', 'technician']:
        flash('You can only assign incidents to engineers or technicians.', 'danger')
        return redirect(url_for('main.view_incident', incident_id=incident_id))

    incident.assigned_to = user.id
    db.session.commit()

    # Add notification for the assigned user
    NotificationManager.add_notification(
        user_id=user.id,
        message=f"You have been assigned a new incident: {incident.description[:20]}",
        notif_type="Incident Assignment",
        incident_id=incident.id,
        assigned_user_id=user.id
    )

    log_activity(current_user.id, "Assigned Incident")
    flash(f'Incident assigned to {user.username}.', 'success')
    return redirect(url_for('main.view_incident', incident_id=incident_id))


@bp.route('/tasks', methods=['GET'])
@login_required
def view_tasks():
    """View tasks categorized by status and priority with filtering options."""
    tasks_by_status = {}
    unassigned_tasks = []
    users = User.query.all()  # Fetch all users for filtering

    # Fetch filter criteria from query parameters
    filter_priority = request.args.get('filter_priority')
    filter_assignee = request.args.get('filter_assignee')
    filter_status = request.args.get('filter_status')

    # Base query
    query = Task.query

    # Apply filters
    if filter_priority:
        query = query.filter_by(priority=filter_priority)
    if filter_assignee:
        query = query.filter_by(assigned_to=filter_assignee)
    if filter_status:
        query = query.filter_by(status=filter_status)

    if current_user.role == 'admin':
        # Admin sees all tasks
        all_tasks = query.all()
        unassigned_tasks = [task for task in all_tasks if task.assigned_to is None]

        # Categorize tasks by status
        for status in ['Not Started', 'In Progress', 'Completed']:
            tasks_by_status[status] = [task for task in all_tasks if task.status == status]

    elif current_user.role in ['engineer', 'technician']:
        # Engineers/Technicians see only their assigned tasks
        assigned_tasks = query.filter_by(assigned_to=current_user.id).all()

        # Categorize tasks by status
        for status in ['Not Started', 'In Progress', 'Completed']:
            tasks_by_status[status] = [task for task in assigned_tasks if task.status == status]

    else:
        flash("You don't have permission to view tasks.", 'danger')
        return redirect(url_for('main.index'))

    return render_template(
        'tasks.html',
        unassigned_tasks=unassigned_tasks,
        tasks_by_status=tasks_by_status,
        users=users
    )




@bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create_task():
    """Create a new task."""
    if current_user.role not in ['admin', 'engineer']:
        flash("You don't have permission to create tasks.", 'danger')
        return redirect(url_for('main.view_tasks'))

    form = TaskForm()
    form.device_id.choices = [(0, 'None')] + [(d.id, d.name) for d in Device.query.all()]
    form.assigned_to.choices = [(u.id, u.username) for u in User.query.filter(User.role.in_(['technician', 'engineer'])).all()]

    if form.validate_on_submit():
        due_date = form.due_date.data
        if isinstance(due_date, date):
            due_date = datetime.combine(due_date, datetime.min.time())
        elif isinstance(due_date, datetime):
            due_date = due_date
        else:
            due_date = None

        task = Task(
            title=form.title.data,
            description=form.description.data,
            device_id=form.device_id.data if form.device_id.data != 0 else None,
            assigned_to=form.assigned_to.data,
            created_by=current_user.id,
            priority=form.priority.data,
            due_date=due_date,
            status='Not Started',
        )
        db.session.add(task)
        db.session.commit()

        # Notify the assigned user
        if task.assigned_to:
            assigned_user = User.query.get(task.assigned_to)
            NotificationManager.add_notification(
                user_id=assigned_user.id,
                message=f"You have been assigned a new task: {task.title}",
                notif_type="Task Assignment",
                task_id=task.id
            )

        log_activity(current_user.id, "Created task ")
        flash('Task created successfully!', 'success')
        return redirect(url_for('main.view_tasks'))

    return render_template('create_task.html', form=form)

@bp.route('/tasks/<int:task_id>', methods=['GET'])
@login_required
def task_details(task_id):
    """View task details."""
    task = Task.query.get_or_404(task_id)

    # Ensure the user has permission to view the task
    if current_user.role not in ['admin', 'engineer', 'technician'] or \
       (current_user.role in ['engineer', 'technician'] and task.assigned_to != current_user.id):
        flash("You don't have permission to view this task.", 'danger')
        return redirect(url_for('main.view_tasks'))

    # Fetch available users (engineers and technicians) if the task is unassigned and the current user is admin
    available_users = None
    if current_user.role == 'admin' and task.assigned_to is None:
        available_users = User.query.filter(User.role.in_(['engineer', 'technician'])).all()

    log_activity(current_user.id, "Viewed task details for task ID")  # Log the activity
    return render_template(
        'task_details.html', 
        task=task, 
        available_users=available_users
    )



@bp.route('/tasks/<int:task_id>/update_status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """Update the status of a task."""
    task = Task.query.get_or_404(task_id)

    # Ensure the current user is assigned to the task or is an admin
    if task.assigned_to != current_user.id and current_user.role != 'admin':
        flash("You are not authorized to update this task.", "danger")
        return redirect(url_for('main.view_tasks'))

    new_status = request.form.get('status')

    # Update the task status
    task.status = new_status
    db.session.commit()

    # Log activity
    log_activity(current_user.id, f"Updated task status to {new_status}")
    if task.status == 'Completed':
        message = f"Task '{task.title}' has been completed by: {current_user.username}."
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            NotificationManager.add_notification(
                user_id=admin.id,  # Send notification to each admin
                message=message,
                notif_type='Task',
                task_id=task.id
            )

    flash("Task status updated successfully!", "success")

    return redirect(url_for('main.task_details', task_id=task.id))

@bp.route('/tasks/assign', methods=['GET', 'POST'])
@login_required
def assign_task():
    """Admin can assign unassigned tasks to engineers or technicians."""
    if current_user.role != 'admin':
        flash("You don't have permission to assign tasks.", 'danger')
        return redirect(url_for('main.view_tasks'))

    # Fetch unassigned tasks
    unassigned_tasks = Task.query.filter_by(assigned_to=None).all()

    # Fetch engineers and technicians for assignment
    available_users = User.query.filter(User.role.in_(['engineer', 'technician'])).all()

    if request.method == 'POST':
        task_id = request.form.get('task_id')
        assigned_user_id = request.form.get('assigned_to')

        task = Task.query.get_or_404(task_id)
        user = User.query.get_or_404(assigned_user_id)

        if user.role not in ['engineer', 'technician']:
            flash('You can only assign tasks to engineers or technicians.', 'danger')
        else:
            task.assigned_to = user.id
            db.session.commit()

            # Notify the assigned user
            NotificationManager.add_notification(
                user_id=user.id,
                message=f"You have been assigned a task: {task.title}",
                notif_type="Task Assignment",
                task_id=task.id
            )
            log_activity(current_user.id, "asigned task ")  # Log the activity

            flash(f'Task "{task.title}" has been assigned to {user.username}.', 'success')

        return redirect(url_for('main.assign_task'))

    return render_template('assign_task.html', tasks=unassigned_tasks, users=available_users)

@bp.route('/tasks/<int:task_id>/assign', methods=['POST'])
@login_required
def assign_task_to_user(task_id):
    """Assign a task to a user."""
    if current_user.role != 'admin':
        flash("You don't have permission to assign tasks.", 'danger')
        return redirect(url_for('main.task_details', task_id=task_id))

    task = Task.query.get_or_404(task_id)
    if task.assigned_to:
        flash('Task is already assigned.', 'danger')
        return redirect(url_for('main.task_details', task_id=task_id))

    assigned_user_id = request.form.get('assigned_to')
    user = User.query.get_or_404(assigned_user_id)

    if user.role not in ['engineer', 'technician']:
        flash('You can only assign tasks to engineers or technicians.', 'danger')
        return redirect(url_for('main.task_details', task_id=task_id))

    task.assigned_to = user.id
    db.session.commit()

    # Notify the assigned user
    NotificationManager.add_notification(
        user_id=user.id,
        message=f"You have been assigned a task: {task.title}",
        notif_type="Task Assignment",
        task_id=task.id
    )
    log_activity(current_user.id, f"Assigned task ID {task.id} to user ID {user.id}")

    flash(f'Task "{task.title}" has been assigned to {user.username}.', 'success')
    return redirect(url_for('main.task_details', task_id=task_id))


# Route for managing users (admin)
@bp.route('/manage_users', methods=['GET'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('main.index'))

    # Get all users from the User model
    users = User.query.all()
    log_activity(current_user.id, 'Viewed user management page')  # Log the activity
    return render_template('manage_users.html', users=users)

# Route for viewing all users
@bp.route('/view_all_users', methods=['GET'])
@login_required
def view_all_users():
    if current_user.role != 'admin':
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('main.index'))

    users = User.query.all()  # Fetch all users from the database
    log_activity(current_user.id, 'Viewed all users')  # Log the activity
    return render_template('view_all_users.html', users=users)

@bp.route('/user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def view_user_details(user_id):
    """Display detailed information about a user and allow assigning devices, tasks, and incidents."""
    user = User.query.get_or_404(user_id)

    # Ensure that the current user has appropriate permissions to view this page
    if current_user.role != 'admin' and current_user.id != user.id:
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('main.index'))

    # Fetch devices, tasks, and incidents for assignment
    devices = Device.query.filter(Device.assigned_to == None).all()
    tasks = Task.query.filter_by(assigned_to=None).all()
    incidents = IncidentReport.query.filter_by(assigned_to=None).all()

    

    if request.method == 'POST':
        # Handling device assignment
        if 'device_id' in request.form:
            device_id = request.form['device_id']
            device = Device.query.get(device_id)

            if device:
                device.assigned_to = user.id  # Assign device to selected user
                db.session.commit()

                # Create a notification for the user
                notification = Notification(
                    user_id=user.id,
                    type='Device Assignment',
                    message=f'Device "{device.name}" has been assigned to you.',
                    is_read=False,
                    assigned_user_id=user.id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(notification)
                db.session.commit()

                log_activity(current_user.id, 'Assigned Device')
                flash(f'Device "{device.name}" assigned.', 'success')
            else:
                flash('Error assigning device. Please try again.', 'danger')

        # Handling task assignment
        elif 'task_id' in request.form:
            task_id = request.form['task_id']
            task = Task.query.get(task_id)

            if task:
                task.assigned_to = user.id  # Assign task to selected user
                db.session.commit()

                # Create a notification for the user
                notification = Notification(
                    user_id=user.id,
                    type='Task Assignment',
                    message=f'Task "{task.title}" has been assigned to you.',
                    is_read=False,
                    assigned_user_id=user.id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(notification)
                db.session.commit()

                log_activity(current_user.id, 'Assigned Task')
                flash(f'Task "{task.title}" assigned.', 'success')

        # Handling incident assignment
        elif 'incident_id' in request.form:
            incident_id = request.form['incident_id']
            incident = IncidentReport.query.get(incident_id)

            if incident:
                incident.assigned_to = user.id  # Assign incident to selected user
                db.session.commit()

                # Create a notification for the user
                notification = Notification(
                    user_id=user.id,
                    type='Incident Assignment',
                    message=f'Incident "{incident.description}" has been assigned to you.',
                    is_read=False,
                    assigned_user_id=user.id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(notification)
                db.session.commit()

                log_activity(current_user.id, 'Assigned Incident')
                flash(f'Incident "{incident.description}" assigned.', 'success')

        return redirect(url_for('main.view_user_details', user_id=user.id))

    log_activity(current_user.id, 'Viewed user detail')
    return render_template(
        'view_user_details.html',
        user=user,
        devices=devices,
        tasks=tasks,
        incidents=incidents,
    )

# Route to delete a user
@bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    # Check if the current user has the necessary permission
    if current_user.role != 'admin':
        flash('You do not have permission to delete users.', 'danger')
        return redirect(url_for('main.index'))

    # Prevent the current user from deleting themselves
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('main.view_user_details', user_id=current_user.id))

    user = User.query.get_or_404(user_id)
    
    # Perform the deletion
    db.session.delete(user)
    db.session.commit()
    
    # Log the activity
    log_activity(current_user.id, f'Deleted user: {user.username}', user=user)  # Log the activity
    
    flash(f'User {user.username} has been deleted.', 'success')
    return redirect(url_for('main.manage_users'))


@bp.route('/reminders', methods=['GET'])
@login_required
def view_reminders():
    """View upcoming maintenance schedules, warranty expiration dates, and task due dates."""
    today = datetime.utcnow()

    # Fetch data
    upcoming_maintenance = Device.query.filter(Device.next_maintenance_date >= today).order_by(Device.next_maintenance_date).all()
    upcoming_warranty_expiry = Device.query.filter(
        Device.warranty_expiry_date >= today,
        Device.warranty_expiry_date <= today + timedelta(days=30)
    ).order_by(Device.warranty_expiry_date).all()
    upcoming_task_due_dates = Task.query.filter(
        Task.due_date >= today,
        Task.due_date <= today + timedelta(days=30)
    ).order_by(Task.due_date).all()

    # Log the activity
    log_activity(current_user.id, 'Viewed reminders')

    # Pass counts for each category
    return render_template(
        'reminders.html',
        upcoming_maintenance=upcoming_maintenance,
        upcoming_warranty_expiry=upcoming_warranty_expiry,
        upcoming_task_due_dates=upcoming_task_due_dates,
        maintenance_count=len(upcoming_maintenance),
        warranty_count=len(upcoming_warranty_expiry),
        task_count=len(upcoming_task_due_dates)
    )

@bp.route('/notifications', methods=['GET'])
@login_required
def view_notifications():
    """
    Route to view all notifications for the current user.
    """
    notifications = NotificationManager.get_user_notifications(current_user.id, limit=10)
    return render_template('notifications.html', notifications=notifications)

@bp.route('/notification/<int:notification_id>/read', methods=['GET'])
@login_required
def mark_notification_read(notification_id):
    """Mark a specific notification as read and redirect to the corresponding detail page."""
    notification = Notification.query.get_or_404(notification_id)

    # Ensure the notification belongs to the current user
    if notification.user_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("main.index"))

    # Mark the notification as read
    notification.is_read = True
    db.session.commit()
    flash("Notification marked as read.", "success")

    # Redirect to the appropriate detail page based on the notification type
    if notification.type == 'Task' or notification.type == 'Task Assignment':
        return redirect(url_for('main.task_details', task_id=notification.task_id))
    elif notification.type == 'Incident' or notification.type == 'Incident Assignment':
        return redirect(url_for('main.view_incident', incident_id=notification.incident_id))
    elif notification.type == 'Device' or notification.type == 'Device Assignment':
        return redirect(url_for('main.device_details', id=notification.device_id))
    elif notification.type == 'Maintenance' or notification.type == 'Maintenance Assignment':
        return redirect(url_for('main.device_details', id=notification.device_id))

    # Default fallback if no conditions are met
    return redirect(url_for('main.view_notifications'))



@bp.route('/trigger_notification')
@login_required
def trigger_notification():
    """
    Route to manually trigger a sample notification (for testing).
    """
    NotificationManager.add_notification(
        user_id=current_user.id,
        message="This is a test notification.",
        notif_type="Task"
    )
    flash("Test notification sent.", "success")
    return redirect(url_for('main.view_notifications'))

@bp.route('/notifications/all')
@login_required
def view_all_notifications():
    """Display all notifications for the current user."""
    notifications = db.session.query(
        Notification,
        User.username.label('assigned_username')
    ).outerjoin(User, Notification.assigned_user_id == User.id)  # Join with the assigned_user_id
    notifications = notifications.filter(Notification.user_id == current_user.id)  # Current user's notifications
    notifications = notifications.order_by(Notification.timestamp.desc()).all()

    return render_template('notifications.html', notifications=notifications)

@bp.route('/notification/<int:notification_id>/remove', methods=['POST'])
@login_required
def remove_notification(notification_id):
    """Remove a specific notification."""
    notification = Notification.query.get_or_404(notification_id)

    # Ensure the notification belongs to the current user
    if notification.user_id != current_user.id:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("main.index"))

    # Remove the notification
    NotificationManager.remove_notification(notification_id)
    flash("Notification removed successfully.", "success")
    return redirect(url_for("main.index"))

@bp.route('/notifications/clear_read', methods=['POST'])
@login_required
def clear_read_notifications():
    """Remove all read notifications for the current user."""
    NotificationManager.clear_read_notifications(current_user.id)
    flash("All read notifications have been removed.", "success")
    return redirect(url_for('main.index'))

@bp.route('/notifications/unread')
@login_required
def view_unread_notifications():
    """Display all unread notifications for the current user."""
    notifications = NotificationManager.get_unread_notifications(current_user.id)
    return render_template('notifications.html', notifications=notifications)


# Route to logout
@bp.route('/logout')

@login_required
def logout():
    log_activity(current_user.id, 'Logged out')  # Log the activity
    logout_user()  # Use Flask-Login's logout_user method
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.login'))  # Redirect to login page after logout