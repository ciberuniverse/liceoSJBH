import os

# SECRET KEYS CONEXIONES Y BDD
SECRET_KEY = os.environ.get("SECRET_KEY") or "324535542d953171e82ff39f647e41baeb53ce0b11f127a8da2fce199f5fd8955c368f1db7c7b1cb32abc6e236bb96d5cd85d65812a7506036fb362c47344ddf"
URL_HOST = os.environ.get("HOST") or "mongodb://localhost:27017/"

CACHE_TYPE = "RedisCache"
REDIS_DB = 0
CACHE_TIMEOUT = 300 
"""Limita el tiempo de duracion de la cache por defecto."""

REDIS_URI = os.environ.get("REDIS_URI") or "redis://default:NfoBZLfIiASwDqkNkhVc3ZMU7oFQgDIE@redis-19586.crce181.sa-east-1-2.ec2.cloud.redislabs.com:19586"
REDIS_PORT = os.environ.get("REDIS_PORT") or 19586
REDIS_HOST = os.environ.get("REDIS_HOST") or "redis-19586.crce181.sa-east-1-2.ec2.cloud.redislabs.com"
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or "NfoBZLfIiASwDqkNkhVc3ZMU7oFQgDIE"

# TEMPLATES DIRs
ROOT_DIR = os.getcwd()
TEMPLATES_DIR = os.path.join(ROOT_DIR, "static", "informes_templates")
MEDIA_DIR = os.path.join(ROOT_DIR, "static", "media")

