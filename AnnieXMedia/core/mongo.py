# Authored By Certified Coders © 2025
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI
from ..logging import LOGGER

LOGGER(__name__).info("Connecting to your Mongo Database...")

if not MONGO_DB_URI or not str(MONGO_DB_URI).strip():
    LOGGER(__name__).error("MONGO_DB_URI is missing! Set MONGO_DB_URI in environment variables.")
    sys.exit(1)

try:
    _mongo_async_ = AsyncIOMotorClient(
        MONGO_DB_URI,
        serverSelectionTimeoutMS=12500,
        connectTimeoutMS=10000,
        maxPoolSize=20,
        minPoolSize=1,
    )
    mongodb = _mongo_async_.Annie
    LOGGER(__name__).info("Connected to your Mongo Database.")
except Exception as e:
    LOGGER(__name__).error(f"Failed to connect to your Mongo Database: {e}")
    sys.exit(1)
