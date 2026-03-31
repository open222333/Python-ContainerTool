import json
from src import FLASK_JSON_PATH

with open(FLASK_JSON_PATH, 'r') as f:
    conf = json.loads(f.read())


class BasicConfig(object):
    """基本設定

    [配置管理](https://dormousehole.readthedocs.io/en/latest/config.html)

    Args:
        object (_type_): _description_

    Returns:
        _type_: _description_
    """    """Base config, uses staging database server."""
    SECRET_KEY = conf['SECRET_KEY']
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = True


class ProductionConfig(BasicConfig):
    DB_SERVER = '192.168.19.32'


class DevelopmentConfig(BasicConfig):
    DB_SERVER = 'localhost'


class TestingConfig(BasicConfig):
    """測試

    Args:
        BasicConfig (_type_): _description_
    """
    TESTING = False,
    DEBUG = False,
    DB_SERVER = 'localhost'
    DATABASE_URI = 'sqlite:///:memory:'
