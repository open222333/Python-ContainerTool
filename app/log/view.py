from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from src.models.restart_log import RestartLog
from src.models.reboot_log import RebootLog

app_log = Blueprint('app_log', __name__)


@app_log.route('/restart', methods=['GET'])
@jwt_required()
def list_restart_logs():
    limit = request.args.get('limit', 200, type=int)
    logs = RestartLog.find_all(limit=limit)
    return jsonify({'success': True, 'data': logs})


@app_log.route('/reboot', methods=['GET'])
@jwt_required()
def list_reboot_logs():
    limit = request.args.get('limit', 200, type=int)
    logs = RebootLog.find_all(limit=limit)
    return jsonify({'success': True, 'data': logs})
