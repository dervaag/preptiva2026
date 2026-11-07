import bcrypt


def password_size_ok(password):
    if not isinstance(password, str):
        return False
    try:
        return 0 < len(password.encode()) <= 72
    except UnicodeError:
        return False


def hash_password(password):
    if not password_size_ok(password):
        raise ValueError('Password harus berisi 1–72 byte UTF-8.')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    if not password_size_ok(password) or not isinstance(hashed, str):
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False
