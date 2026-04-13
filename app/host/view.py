from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.host import Host
from src.models.restart_log import RestartLog
from src.models.reboot_log import RebootLog
from src.container import ContainerTool, RestrictedContainerTool
from src.permissions import require_role

app_host = Blueprint('host', __name__)


def _get_tool(h: dict, cred_key: str = 'credential_restart'):
    """從主機資料建立操作工具實例。

    cred_key:
        'credential_restart' — 用於容器查詢與重啟（預設）
        'credential_reboot'  — 用於主機重開機
    向下相容舊格式 credentials 陣列及平鋪欄位。

    conn_type（憑證內欄位）:
        'standard'   — ContainerTool（標準 SSH，可執行多步驟指令）
        'restricted' — RestrictedContainerTool（authorized_keys command= 白名單模式）
    """
    c = h.get(cred_key) or {}
    if not c:
        creds = h.get('credentials') or []
        c = creds[0] if creds else {}

    common = dict(
        host=h['host'],
        ssh_user=c.get('ssh_user') or h.get('ssh_user', 'root'),
        ssh_port=h.get('ssh_port', 22),
        ssh_timeout=10,
        ssh_key_path=c.get('ssh_key_path') or h.get('ssh_key_path'),
        ssh_password=c.get('ssh_password') or h.get('ssh_password'),
    )

    if c.get('conn_type') == 'restricted':
        return RestrictedContainerTool(**common)

    return ContainerTool(use_sudo=not c.get('is_root', h.get('is_root', True)), **common)


def _validate_credential(c, label: str):
    """驗證單一憑證物件，回傳錯誤訊息字串或 None。"""
    if not c or not isinstance(c, dict):
        return f'{label} 不得為空'
    if not c.get('ssh_user'):
        return f'{label} 的 SSH 使用者不得為空'
    return None


@app_host.route('/', methods=['GET'])
@jwt_required()
def list_hosts():
    """
    列出所有主機
    ---
    tags:
      - Host
    security:
      - Bearer: []
    responses:
      200:
        description: 主機列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
    """
    return jsonify({'success': True, 'data': Host.find_all()})


@app_host.route('/', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_host():
    """
    新增主機
    ---
    tags:
      - Host
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
            - host
            - ssh_user
          properties:
            name:
              type: string
              example: server-01
            host:
              type: string
              example: 192.168.1.100
            ssh_user:
              type: string
              example: root
            ssh_port:
              type: integer
              example: 22
            ssh_key_path:
              type: string
              example: ~/.ssh/id_rsa
            ssh_password:
              type: string
            description:
              type: string
    responses:
      201:
        description: 新增成功
      400:
        description: 缺少必要欄位
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '缺少請求參數'}), 400

    for field in ['name', 'host']:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'缺少欄位: {field}'}), 400

    err = _validate_credential(data.get('credential_reboot'), '重啟主機帳號')
    if err:
        return jsonify({'success': False, 'message': err}), 400
    err = _validate_credential(data.get('credential_restart'), '重啟容器帳號')
    if err:
        return jsonify({'success': False, 'message': err}), 400

    host_data = {
        'name': data['name'],
        'host': data['host'],
        'ssh_port': data.get('ssh_port', 22),
        'credential_reboot': data['credential_reboot'],
        'credential_restart': data['credential_restart'],
        'description': data.get('description', ''),
    }
    host_id = Host.create(host_data)
    return jsonify({'success': True, 'id': host_id}), 201


@app_host.route('/<host_id>', methods=['GET'])
@jwt_required()
def get_host(host_id):
    """
    取得單一主機
    ---
    tags:
      - Host
    security:
      - Bearer: []
    parameters:
      - in: path
        name: host_id
        type: string
        required: true
    responses:
      200:
        description: 主機資訊
      404:
        description: 主機不存在
    """
    h = Host.find_by_id(host_id)
    if not h:
        return jsonify({'success': False, 'message': '主機不存在'}), 404
    return jsonify({'success': True, 'data': h})


@app_host.route('/<host_id>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_host(host_id):
    """
    更新主機資訊
    ---
    tags:
      - Host
    security:
      - Bearer: []
    parameters:
      - in: path
        name: host_id
        type: string
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
            host:
              type: string
            ssh_user:
              type: string
            ssh_port:
              type: integer
            ssh_key_path:
              type: string
            ssh_password:
              type: string
            description:
              type: string
    responses:
      200:
        description: 更新成功
      404:
        description: 主機不存在或無變更
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '缺少請求參數'}), 400

    allowed = ['name', 'host', 'ssh_port', 'credential_reboot', 'credential_restart', 'description',
               'credentials', 'ssh_user', 'ssh_key_path', 'ssh_password', 'is_root']  # 後四者向下相容
    update_data = {k: v for k, v in data.items() if k in allowed}
    for cred_key, label in [('credential_reboot', '重啟主機帳號'), ('credential_restart', '重啟容器帳號')]:
        if cred_key in update_data:
            err = _validate_credential(update_data[cred_key], label)
            if err:
                return jsonify({'success': False, 'message': err}), 400
    if not update_data:
        return jsonify({'success': False, 'message': '無可更新欄位'}), 400

    ok = Host.update(host_id, update_data)
    if not ok:
        return jsonify({'success': False, 'message': '更新失敗或主機不存在'}), 404
    return jsonify({'success': True})


@app_host.route('/<host_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def delete_host(host_id):
    """
    刪除主機
    ---
    tags:
      - Host
    security:
      - Bearer: []
    parameters:
      - in: path
        name: host_id
        type: string
        required: true
    responses:
      200:
        description: 刪除成功
      404:
        description: 主機不存在
    """
    ok = Host.delete(host_id)
    if not ok:
        return jsonify({'success': False, 'message': '主機不存在'}), 404
    return jsonify({'success': True})


@app_host.route('/<host_id>/containers', methods=['GET'])
@jwt_required()
def list_containers(host_id):
    """
    列出主機上的所有容器
    ---
    tags:
      - Host
    security:
      - Bearer: []
    parameters:
      - in: path
        name: host_id
        type: string
        required: true
    responses:
      200:
        description: 容器列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  name:
                    type: string
                  image:
                    type: string
                  status:
                    type: string
                  state:
                    type: string
      404:
        description: 主機不存在
      500:
        description: SSH 連線失敗
    """
    h = Host.find_by_id(host_id)
    if not h:
        return jsonify({'success': False, 'message': '主機不存在'}), 404

    tool = _get_tool(h)
    containers, err = tool.list_containers()
    if containers is None:
        return jsonify({'success': False, 'message': f'SSH 連線失敗：{err}'}), 500
    return jsonify({'success': True, 'data': containers})


@app_host.route('/<host_id>/containers/<container_name>/restart', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def restart_container(host_id, container_name):
    """
    重啟指定容器
    ---
    tags:
      - Host
    security:
      - Bearer: []
    parameters:
      - in: path
        name: host_id
        type: string
        required: true
      - in: path
        name: container_name
        type: string
        required: true
    responses:
      200:
        description: 重啟結果
      404:
        description: 主機不存在
    """
    h = Host.find_by_id(host_id)
    if not h:
        return jsonify({'success': False, 'message': '主機不存在'}), 404

    tool = _get_tool(h)
    ok, reason = tool.restart(container_name)
    RestartLog.create(
        username=get_jwt_identity(),
        host_name=h['name'],
        host_ip=h['host'],
        container_name=container_name,
        success=ok,
        reason=reason
    )
    return jsonify({'success': ok, 'reason': reason})


@app_host.route('/<host_id>/containers/batch-restart', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def batch_restart_containers(host_id):
    h = Host.find_by_id(host_id)
    if not h:
        return jsonify({'success': False, 'message': '主機不存在'}), 404

    data = request.get_json()
    container_names = data.get('containers', []) if data else []
    if not container_names:
        return jsonify({'success': False, 'message': '未指定容器'}), 400

    username = get_jwt_identity()

    def restart_one(name):
        tool = _get_tool(h)
        ok, reason = tool.restart(name)
        RestartLog.create(
            username=username,
            host_name=h['name'],
            host_ip=h['host'],
            container_name=name,
            success=ok,
            reason=reason
        )
        return {'container': name, 'success': ok, 'reason': reason}

    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(restart_one, name): name for name in container_names}
        for future in as_completed(futures):
            results.append(future.result())

    return jsonify({'success': True, 'results': results})


@app_host.route('/<host_id>/reboot', methods=['POST'])
@jwt_required()
@require_role('admin')
def reboot_host(host_id):
    h = Host.find_by_id(host_id)
    if not h:
        return jsonify({'success': False, 'message': '主機不存在'}), 404

    tool = _get_tool(h, cred_key='credential_reboot')
    ok, reason = tool.reboot_host()
    RebootLog.create(
        username=get_jwt_identity(),
        host_name=h['name'],
        host_ip=h['host'],
        success=ok,
        reason=reason
    )
    return jsonify({'success': ok, 'reason': reason})
