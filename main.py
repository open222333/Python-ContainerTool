import json
import secrets
import sys
from os import makedirs
from os.path import join, exists

from src import LOG_LEVEL, LOG_FILE_DISABLE, LOG_PATH, SSH_USER, SSH_KEY_PATH, SSH_PASSWORD, SSH_PORT, SSH_TIMEOUT
from src.common_tool.src.logger import Log
from src.container import ContainerTool
from argparse import ArgumentParser

logger = Log('container-tool')
logger.set_level(LOG_LEVEL)
if not LOG_FILE_DISABLE:
    logger.set_log_path(LOG_PATH)
    logger.set_date_handler()
logger.set_msg_handler()

FLASK_JSON_PATH = join('conf', 'flask.json')


SSH_DIR = 'ssh'


def cmd_gen_ssh_key(name: str, force: bool):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend

    if not exists(SSH_DIR):
        makedirs(SSH_DIR)

    private_key_path = join(SSH_DIR, name)
    public_key_path = f'{private_key_path}.pub'

    if exists(private_key_path) and not force:
        print(f'{private_key_path} 已存在，若要強制重新產生請加上 --force')
        return

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

    with open(public_key_path, 'wb') as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ))

    import stat
    import os
    os.chmod(private_key_path, stat.S_IRUSR | stat.S_IWUSR)

    print(f'私鑰：{private_key_path}')
    print(f'公鑰：{public_key_path}')
    print(f'請將公鑰內容加入遠端主機的 ~/.ssh/authorized_keys')


def cmd_secret_key(force: bool):
    with open(FLASK_JSON_PATH, 'r') as f:
        conf = json.load(f)

    if conf.get('SECRET_KEY') and not force:
        print('SECRET_KEY 已存在，若要強制更新請加上 --force')
        return

    conf['SECRET_KEY'] = secrets.token_hex(32)
    with open(FLASK_JSON_PATH, 'w') as f:
        json.dump(conf, f, indent=2)
    print(f'SECRET_KEY 已寫入 {FLASK_JSON_PATH}')


if __name__ == '__main__':
    parser = ArgumentParser(description='遠端 Docker 容器管理工具')
    parser.add_argument('-H', '--host', type=str, help='遠端主機 IP 或 hostname', default=None)
    parser.add_argument('-c', '--container', type=str, help='容器名稱', default=None)
    parser.add_argument('-p', '--port', type=int, help='SSH port，預設 22', default=None)
    parser.add_argument('-u', '--user', type=str, help='SSH 使用者，預設讀取 config.ini', default=None)
    parser.add_argument('-k', '--key', type=str, help='SSH 私鑰路徑，預設讀取 config.ini', default=None)
    parser.add_argument('--action', choices=['restart', 'status'], default='restart',
                        help='執行動作: restart(重啟) / status(查狀態)，預設 restart')
    parser.add_argument(
        '-l', '--log_level', type=str,
        help='設定 log 等級 DEBUG,INFO,WARNING,ERROR,CRITICAL',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], required=False
    )
    parser.add_argument('--gen-secret-key', action='store_true', help='產生 SECRET_KEY 並寫入 conf/flask.json')
    parser.add_argument('--gen-ssh-key', action='store_true', help='產生 SSH 金鑰對並存入 ssh/ 目錄')
    parser.add_argument('--ssh-key-name', type=str, default='id_rsa', help='SSH 私鑰檔名，預設 id_rsa')
    parser.add_argument('--force', action='store_true', help='強制覆蓋已存在的檔案（搭配 --gen-secret-key 或 --gen-ssh-key）')
    args = parser.parse_args()

    if args.gen_secret_key:
        cmd_secret_key(force=args.force)
        sys.exit(0)

    if args.gen_ssh_key:
        cmd_gen_ssh_key(name=args.ssh_key_name, force=args.force)
        sys.exit(0)

    if not args.host or not args.container:
        parser.error('容器操作需要 -H (主機) 與 -c (容器名稱)')

    if args.log_level:
        logger.set_level(args.log_level)

    tool = ContainerTool(
        host=args.host,
        ssh_user=args.user or SSH_USER,
        ssh_port=args.port or SSH_PORT,
        ssh_timeout=SSH_TIMEOUT,
        ssh_key_path=args.key or SSH_KEY_PATH,
        ssh_password=SSH_PASSWORD,
        logger=logger,
    )

    if args.action == 'restart':
        ok, reason = tool.restart(args.container)
        if not ok:
            print(f'[FAIL] 重啟失敗: {reason}')
    elif args.action == 'status':
        state = tool.status(args.container)
        if state:
            print(f'[{args.host}] 容器 {args.container} 狀態: {state}')
