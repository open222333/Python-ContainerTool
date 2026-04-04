from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import User, ROLES
from src.permissions import require_role

app_user = Blueprint('app_user', __name__)


@app_user.route('/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_users():
    return jsonify({'success': True, 'data': User.find_all()})


@app_user.route('/', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_user():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '缺少請求參數'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')

    if not username or not password:
        return jsonify({'success': False, 'message': 'username 或 password 不得為空'}), 400

    if role not in ROLES:
        return jsonify({'success': False, 'message': f'無效的角色，可用值：{", ".join(ROLES)}'}), 400

    if User.find_by_username(username):
        return jsonify({'success': False, 'message': '使用者已存在'}), 409

    user_id = User.create(username, password, role=role)
    return jsonify({'success': True, 'id': user_id}), 201


@app_user.route('/<user_id>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_user(user_id):
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '缺少請求參數'}), 400

    password = data.get('password') or None
    role = data.get('role') or None

    if role and role not in ROLES:
        return jsonify({'success': False, 'message': f'無效的角色，可用值：{", ".join(ROLES)}'}), 400

    if not password and not role:
        return jsonify({'success': False, 'message': '請提供 password 或 role'}), 400

    if not User.update(user_id, password=password, role=role):
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    return jsonify({'success': True})


@app_user.route('/<user_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_user(user_id):
    current = get_jwt_identity()
    user = User.find_by_username(current)
    if user and str(user['_id']) == user_id:
        return jsonify({'success': False, 'message': '無法刪除自己的帳號'}), 400

    if not User.delete(user_id):
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    return jsonify({'success': True})
