import os

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from aioredis import Redis
import boto3

UVICORN_HOST = os.environ.get("UVICORN_HOST", "127.0.0.1")
UVICORN_PORT = os.environ.get("UVICORN_PORT", 8000)

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "media")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "database")
MONGODB_COLLECTION_NAME = os.environ.get("MONGODB_COLLECTION_NAME", "your_collection")

# Initialize FastAPI app
app = FastAPI()

# Initialize MongoDB client
mongo_client = AsyncIOMotorClient(MONGODB_URL)
mongo_db = mongo_client[MONGODB_DB_NAME]

# Initialize Redis client
redis: Redis = None

# Initialize S3 client
s3_client = boto3.client('s3')


@app.on_event("startup")
async def startup_db_client():
    # redis setup?
    pass


@app.on_event("shutdown")
async def shutdown_db_client():
    # close connections
    pass


@app.get("/get-users")
async def get_users(id: int | None = None, uid: int | None = None, name: str | None = None, gender: str | None = None,
                    email: str | None = None, phone: str | None = None, dept: str | None = None,
                    grade: str | None = None, language: str | None = None, region: str | None = None,
                    role: str | None = None, preferTags: str | None = None, obtainedCredits: int | None = None):
    params = locals()
    users_collection = mongo_db["users"]
    query = {}
    for key, value in params.items():
        if value is not None:
            query[key] = value

    return await users_collection.find(query).to_list()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=UVICORN_HOST, port=UVICORN_PORT)
