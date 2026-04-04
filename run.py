import json
import secrets
from os.path import join

_FLASK_JSON_PATH = join('conf', 'flask.json')
with open(_FLASK_JSON_PATH, 'r') as _f:
    _flask_conf = json.load(_f)

if not _flask_conf.get('SECRET_KEY'):
    _flask_conf['SECRET_KEY'] = secrets.token_hex(32)
    with open(_FLASK_JSON_PATH, 'w') as _f:
        json.dump(_flask_conf, _f, indent=2)
    print('[init] 已自動產生 SECRET_KEY 並寫入 conf/flask.json')

from app import create_app
from conf.config import TestingConfig
from src.models.user import User
from src import FLASK_PORT


app = create_app(TestingConfig)

admin = User.find_by_username('admin')
if not admin:
    User.create('admin', 'admin', role='admin')
    print('[init] 已建立預設帳號 admin / admin，請登入後立即修改密碼')
elif not admin.get('role'):
    User.update(str(admin['_id']), role='admin')
    print('[init] 已修正 admin 帳號 role 為 admin')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=True)
