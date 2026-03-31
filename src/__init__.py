from configparser import ConfigParser
from os.path import exists, join
from os import makedirs
import logging


config = ConfigParser()
config.read(join('conf', 'config.ini'))


# logs相關參數
# 關閉log功能 輸入選項 (true, True, 1) 預設 不關閉
LOG_DISABLE = config.getboolean('LOG', 'LOG_DISABLE', fallback=False)
# logs路徑 預設 logs
LOG_PATH = config.get('LOG', 'LOG_PATH', fallback='logs')
# 設定紀錄log等級 DEBUG,INFO,WARNING,ERROR,CRITICAL 預設WARNING
LOG_LEVEL = config.get('LOG', 'LOG_LEVEL', fallback='WARNING')
# 關閉紀錄log檔案 輸入選項 (true, True, 1)  預設 不關閉
LOG_FILE_DISABLE = config.getboolean('LOG', 'LOG_FILE_DISABLE', fallback=False)

# 建立log資料夾
if not exists(LOG_PATH) and not LOG_DISABLE:
    makedirs(LOG_PATH)

if LOG_DISABLE:
    logging.disable()


# flask json 設定檔路徑 預設值 conf/flask.json
FLASK_JSON_PATH = config.get('SETTING', 'FLASK_JSON_PATH', fallback=join('conf', 'flask.json'))
