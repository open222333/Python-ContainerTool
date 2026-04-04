from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from src.models.user import User

ROLE_LEVELS = {'admin': 3, 'operator': 2, 'viewer': 1}


def require_role(*roles):
    """限制只有指定角色可以存取"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            username = get_jwt_identity()
            user = User.find_by_username(username)
            if not user or user.get('role') not in roles:
                return jsonify({'success': False, 'message': '權限不足'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
