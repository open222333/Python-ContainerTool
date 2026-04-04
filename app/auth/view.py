from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from src.models.user import User

app_auth = Blueprint('auth', __name__)


@app_auth.route('/login', methods=['POST'])
def login():
    """
    帳號密碼登入，回傳 JWT token
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - password
          properties:
            username:
              type: string
              example: admin
            password:
              type: string
              example: secret
    responses:
      200:
        description: 登入成功，回傳 token
        schema:
          type: object
          properties:
            success:
              type: boolean
            token:
              type: string
      401:
        description: 帳號或密碼錯誤
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '缺少請求參數'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'message': 'username 或 password 不得為空'}), 400

    user = User.find_by_username(username)
    if not user or not User.check_password(password, user['password']):
        return jsonify({'success': False, 'message': '帳號或密碼錯誤'}), 401

    token = create_access_token(identity=username)
    return jsonify({'success': True, 'token': token, 'role': user.get('role', 'viewer')})
