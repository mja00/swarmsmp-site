from .models import AuditLog, db, User


def log_login(user: User) -> AuditLog:
    log_entry = AuditLog(
        user_id=user.id,
        action="LOGIN"
    )
    db.session.add(log_entry)
    db.session.commit()
    return log_entry
    