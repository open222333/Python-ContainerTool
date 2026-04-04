from datetime import datetime
from bson import ObjectId
import bcrypt
from src.mongo import get_db

ROLES = ['admin', 'operator', 'viewer']


class User:
    COLLECTION = 'users'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        users = cls._col().find({}, {'password': 0})
        return [{'_id': str(u['_id']), **{k: v for k, v in u.items() if k != '_id'}} for u in users]

    @classmethod
    def find_by_username(cls, username: str) -> dict:
        return cls._col().find_one({'username': username})

    @classmethod
    def create(cls, username: str, password: str, role: str = 'viewer') -> str:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        result = cls._col().insert_one({
            'username': username,
            'password': hashed.decode(),
            'role': role,
            'created_at': datetime.utcnow()
        })
        return str(result.inserted_id)

    @classmethod
    def update(cls, user_id: str, password: str = None, role: str = None) -> bool:
        fields = {}
        if password:
            fields['password'] = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        if role:
            fields['role'] = role
        if not fields:
            return False
        result = cls._col().update_one({'_id': ObjectId(user_id)}, {'$set': fields})
        return result.matched_count > 0

    @classmethod
    def delete(cls, user_id: str) -> bool:
        result = cls._col().delete_one({'_id': ObjectId(user_id)})
        return result.deleted_count > 0

    @staticmethod
    def check_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
