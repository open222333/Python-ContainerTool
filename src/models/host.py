from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


class Host:
    COLLECTION = 'hosts'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        hosts = []
        for h in cls._col().find():
            h['_id'] = str(h['_id'])
            hosts.append(h)
        return hosts

    @classmethod
    def find_by_id(cls, host_id: str) -> dict:
        try:
            h = cls._col().find_one({'_id': ObjectId(host_id)})
            if h:
                h['_id'] = str(h['_id'])
            return h
        except Exception:
            return None

    @classmethod
    def create(cls, data: dict) -> str:
        data['created_at'] = datetime.utcnow()
        result = cls._col().insert_one(data)
        return str(result.inserted_id)

    @classmethod
    def update(cls, host_id: str, data: dict) -> bool:
        try:
            result = cls._col().update_one(
                {'_id': ObjectId(host_id)},
                {'$set': data}
            )
            return result.modified_count > 0
        except Exception:
            return False

    @classmethod
    def delete(cls, host_id: str) -> bool:
        try:
            result = cls._col().delete_one({'_id': ObjectId(host_id)})
            return result.deleted_count > 0
        except Exception:
            return False
