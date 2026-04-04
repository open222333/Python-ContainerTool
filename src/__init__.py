from configparser import ConfigParser
from os.path import exists, join
from os import makedirs, environ
import logging


FLASK_JSON_PATH = join('conf', 'flask.json')

config = ConfigParser()
config.read(join('conf', 'config.ini'))


# logs相關參數
# 關閉log功能 輸入選項 (true, True, 1) 預設 不關閉
LOG_DISABLE = config.getboolean('LOG', 'LOG_DISABLE', fallback=False)
# logs路徑 預設 logs
LOG_PATH = config.get('LOG', 'LOG_PATH', fallback='logs')
# 設定紀錄log等級 DEBUG,INFO,WARNING,ERROR,CRITICAL 預設WARNING
LOG_LEVEL = config.get('LOG', 'LOG_LEVEL', fallback='WARNING')
# 關閉紀錄log檔案 輸入選項 (true, True, 1)  預設 關閉
LOG_FILE_DISABLE = config.getboolean('LOG', 'LOG_FILE_DISABLE', fallback=True)

# 建立log資料夾
if not exists(LOG_PATH) and not LOG_DISABLE:
    makedirs(LOG_PATH)

if LOG_DISABLE:
    logging.disable()


# SSH 連線參數
SSH_USER = config.get('SSH', 'SSH_USER', fallback='root')
SSH_KEY_PATH = config.get('SSH', 'SSH_KEY_PATH', fallback=None)
SSH_PASSWORD = config.get('SSH', 'SSH_PASSWORD', fallback=None)
SSH_PORT = config.getint('SSH', 'SSH_PORT', fallback=22)
SSH_TIMEOUT = config.getint('SSH', 'SSH_TIMEOUT', fallback=10)

# Flask 參數
FLASK_PORT = int(environ.get('FLASK_PORT', 5000))
JWT_ACCESS_TOKEN_EXPIRES_HOURS = int(environ.get('JWT_ACCESS_TOKEN_EXPIRES_HOURS', 8))

# MongoDB 連線參數
MONGO_URI = config.get('MONGO', 'MONGO_URI', fallback='mongodb://localhost:27017')
MONGO_DB = config.get('MONGO', 'MONGO_DB', fallback='container_tool')
