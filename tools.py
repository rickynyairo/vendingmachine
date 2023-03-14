import jwt
from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime, timedelta


def auth_required(role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Authorization header is missing'}), 401
            parts = auth_header.split()
            if parts[0].lower() != 'bearer':
                return jsonify({'error': 'Authorization header must start with Bearer'}), 401
            elif len(parts) == 1:
                return jsonify({'error': 'Token not found'}), 401
            elif len(parts) > 2:
                return jsonify({'error': 'Authorization header must be Bearer + \s + token'}), 401
            token = parts[1]
            try:
                decoded_token = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
                user_role = decoded_token.get('role', 'guest')
                if user_role not in role:
                    return jsonify({'error': 'User does not have the required role'}), 403
                request.user_id = decoded_token.get('sub')
            except jwt.exceptions.InvalidTokenError:
                return jsonify({'error': 'Token is invalid or expired'}), 401
            # If the user has the required role, call the wrapped function.
            return func(*args, **kwargs)
        return wrapper
    return decorator

def generate_token(user_id, role):
    payload = {
        'sub': user_id,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=1),
        'role': role
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    return token