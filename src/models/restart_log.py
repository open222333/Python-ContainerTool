from datetime import datetime
from src.mongo import get_db


class RestartLog:
    COLLECTION = 'restart_logs'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, username: str, host_name: str, host_ip: str,
               container_name: str, success: bool, reason: str = '') -> str:
        result = cls._col().insert_one({
            'username': username,
            'host_name': host_name,
            'host_ip': host_ip,
            'container_name': container_name,
            'success': success,
            'reason': reason,
            'created_at': datetime.utcnow()
        })
        return str(result.inserted_id)

    @classmethod
    def find_all(cls, limit: int = 200) -> list:
        logs = cls._col().find({}, {'_id': 0}).sort('created_at', -1).limit(limit)
        return list(logs)
