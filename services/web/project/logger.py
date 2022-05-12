from .models import AuditLog, db, User


def log_login(user: User) -> AuditLog:
    log_entry = AuditLog(
        user_id=user.id,
        action="LOGIN"
    )
    db.session.add(log_entry)
    db.session.commit()
    return log_entry


def log_dev_status(user: User, status: bool, target: User) -> AuditLog:
    log_entry = AuditLog(
        user_id=user.id,
        action=f"DEV_STATUS {status}",
        target_id=target.id,
        target_type="USER"
    )
    db.session.add(log_entry)
    db.session.commit()
    return log_entry


def log_staff_status(user: User, status: bool, target: User) -> AuditLog:
    log_entry = AuditLog(
        user_id=user.id,
        action=f"STAFF_STATUS {status}",
        target_id=target.id,
        target_type="USER"
    )
    db.session.add(log_entry)
    db.session.commit()
    return log_entry


def log_connect(user: User) -> AuditLog:
    log_entry = AuditLog(
        user_id=user.id,
        action="CONNECT"
    )
    db.session.add(log_entry)
    db.session.commit()
    return log_entry
    