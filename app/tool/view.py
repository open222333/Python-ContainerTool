import os
import stat
from os import makedirs
from os.path import join, exists

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from src.permissions import require_role

app_tool = Blueprint('tool', __name__)

SSH_DIR = 'ssh'


@app_tool.route('/generate-ssh-key', methods=['POST'])
@jwt_required()
@require_role('admin')
def generate_ssh_key():
    """
    產生 SSH 金鑰對
    ---
    tags:
      - Tool
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              example: id_rsa
              description: 私鑰檔名（存於 ssh/ 目錄）
            force:
              type: boolean
              example: false
              description: 強制覆蓋已存在的金鑰
    responses:
      200:
        description: 產生成功，回傳公鑰內容
        schema:
          type: object
          properties:
            success:
              type: boolean
            public_key:
              type: string
            private_key_path:
              type: string
            public_key_path:
              type: string
            message:
              type: string
      400:
        description: 金鑰名稱不合法
      409:
        description: 金鑰已存在（未指定強制覆蓋）
      500:
        description: 產生失敗
    """
    data = request.get_json() or {}
    name = data.get('name', 'id_rsa').strip()
    force = bool(data.get('force', False))

    if not name or '/' in name or '\\' in name or name.startswith('.'):
        return jsonify({'success': False, 'message': '金鑰名稱不合法'}), 400

    if not exists(SSH_DIR):
        makedirs(SSH_DIR)

    private_key_path = join(SSH_DIR, name)
    public_key_path = f'{private_key_path}.pub'

    if exists(private_key_path) and not force:
        pub_key = ''
        if exists(public_key_path):
            with open(public_key_path, 'r') as f:
                pub_key = f.read().strip()
        return jsonify({
            'success': False,
            'exists': True,
            'public_key': pub_key,
            'private_key_path': private_key_path,
            'public_key_path': public_key_path,
            'message': f'{private_key_path} 已存在，若要強制重新產生請勾選「強制覆蓋」',
        }), 409

    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )

        with open(private_key_path, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=serialization.NoEncryption()
            ))

        public_key_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        with open(public_key_path, 'wb') as f:
            f.write(public_key_bytes)

        os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)

        return jsonify({
            'success': True,
            'public_key': public_key_bytes.decode(),
            'private_key_path': private_key_path,
            'public_key_path': public_key_path,
            'message': f'金鑰已產生：{private_key_path}',
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'產生失敗：{str(e)}'}), 500


@app_tool.route('/ssh-keys', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_ssh_keys():
    """
    列出已產生的 SSH 公鑰清單
    ---
    tags:
      - Tool
    security:
      - Bearer: []
    responses:
      200:
        description: 公鑰清單
    """
    keys = []
    if exists(SSH_DIR):
        for fname in sorted(os.listdir(SSH_DIR)):
            if fname.endswith('.pub'):
                pub_path = join(SSH_DIR, fname)
                try:
                    with open(pub_path, 'r') as f:
                        content = f.read().strip()
                    name = fname[:-4]
                    keys.append({
                        'name': name,
                        'public_key': content,
                        'private_key_path': join(SSH_DIR, name),
                        'public_key_path': pub_path,
                    })
                except Exception:
                    pass
    return jsonify({'success': True, 'data': keys})
