import os
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.database import Database

env_path: Path = Path(__file__).resolve().parents[1] / '.env.dev.local'
file_values: dict[str, str | None] = dotenv_values(env_path, encoding='utf-8-sig', interpolate=False)


def _value(name: str, default: str) -> str:
    value: str | None = os.environ.get(name, file_values.get(name, default))
    return value.strip() if value is not None else ''


mongo_uri: str = _value('GAIA_MONGODB_URI', 'mongodb://127.0.0.1:27017/')
mongo_database: str = _value('GAIA_MONGODB_DATABASE', 'TFM')
http_host: str = _value('GAIA_HTTP_HOST', 'localhost')
http_port: int = int(_value('GAIA_HTTP_PORT', '5000'))

if not mongo_uri or not mongo_database:
    raise ValueError('Configura GAIA_MONGODB_URI y GAIA_MONGODB_DATABASE.')
if not http_host:
    raise ValueError('Configura GAIA_HTTP_HOST.')
if not 1 <= http_port <= 65535:
    raise ValueError('GAIA_HTTP_PORT debe estar entre 1 y 65535.')

client: MongoClient[dict[str, object]] = MongoClient(mongo_uri, connect=False)
db: Database[dict[str, object]] = client[mongo_database]
