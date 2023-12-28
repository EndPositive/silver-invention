import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import boto3
import redis
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorClient
from redis import Redis

UVICORN_HOST = os.environ.get("UVICORN_HOST", "127.0.0.1")
UVICORN_PORT = os.environ.get("UVICORN_PORT", 8000)

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://root:root@localhost:27017")

REDIS_MASTER_URL = os.environ.get("REDIS_MASTER_URL", "redis://@localhost:6379/0")
REDIS_REPLICA_URL = os.environ.get("REDIS_REPLICA_URL", "redis://@localhost:6379/0")

S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "media")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "PASSWORD")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "USERNAME")

MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "database")

# Initialize MongoDB client
mongo_client = AsyncIOMotorClient(MONGODB_URL)
mongo_db = mongo_client[MONGODB_DB_NAME]

# Initialize Redis client with a master and replica
redis_master: Redis = redis.Redis.from_url(REDIS_MASTER_URL, db=0)
redis_replica: Redis = redis.Redis.from_url(REDIS_REPLICA_URL, db=0)

# Initialize S3 client from S3 bucket name and URL
s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    config=boto3.session.Config(signature_version='s3v4', region_name='us-east-1')
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # test if mongo client is connected
    print("waiting for mongodb connection...")
    print(await mongo_client.server_info())
    # test if redis master and replica are connected
    print("waiting for redis master connection...")
    print(redis_master.ping())
    print("waiting for redis replica connection...")
    print(redis_replica.ping())
    # test if s3 is connected
    print("waiting for s3 connection...")
    print(s3.list_buckets())
    yield
    redis_master.close()
    redis_replica.close()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


async def set_cache(data, key: str):
    return redis_master.set(
        key,
        json.dumps(data),
        ex=120,
    )


async def get_cache(key: str):
    result = redis_replica.get(key)
    if not result:
        return None

    return json.loads(result)


def parse_output(output):
    for r in output:
        r["id"] = str(r.pop("_id"))
    return output


def build_cache_key(collection, skip, limit, query):
    cache_components = {
        'collection': collection.name,  # assuming collection has a 'name' attribute
        'skip': skip,
        'limit': limit,
        'query': query,
    }

    cache_key = json.dumps(cache_components, sort_keys=True)
    return cache_key


async def get_data(background_tasks: BackgroundTasks, collection, skip: int = 0, limit: int = 10, query: dict = {}):
    cache_key = build_cache_key(collection, skip, limit, query)

    cached = await get_cache(cache_key)
    if cached:
        return cached

    result = await collection.find(query).skip(skip).limit(limit).to_list(limit)

    background_tasks.add_task(set_cache, result, cache_key)

    return parse_output(result)


async def get_data_by_query(collection, background_tasks: BackgroundTasks, **kwargs):
    # Exclude specific variables from the query parameters
    query = {k: v for k, v in sorted(kwargs.items()) if v is not None}

    # Fetch data using the common get_data function
    return await get_data(background_tasks=background_tasks, collection=collection, query=query)


def process_articles_response(rows):
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            (executor.submit(
                s3.get_object,
                Bucket=S3_BUCKET_NAME,
                Key=row["text"]
            ), row)
            for row in rows
        ]

        for (future, row) in futures:
            row["text"] = future.result()["Body"].read().decode("utf-8")

    for row in rows:
        row["image"] = [
            s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": S3_BUCKET_NAME,
                    "Key": image_file_name
                }
            )
            for image_file_name in row["image"].split(",")
        ]

        row["video"] = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": S3_BUCKET_NAME,
                "Key": row["video"]
            }
        )

    return rows


@app.get("/", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url='/docs')


@app.get("/users")
async def get_users(background_tasks: BackgroundTasks, region: str | None):
    return await get_data_by_query(mongo_db["users"], **locals())


@app.get("/articles")
async def get_articles(background_tasks: BackgroundTasks, skip: int = 0, limit: int = 10):
    rows = await get_data(background_tasks, mongo_db["articles"], skip, limit)
    return process_articles_response(rows)


@app.get("/user")
async def get_user_by(background_tasks: BackgroundTasks, id: int | None = None, uid: int | None = None,
                      name: str | None = None, gender: str | None = None, email: str | None = None,
                      phone: str | None = None, dept: str | None = None, grade: str | None = None,
                      language: str | None = None, region: str | None = None, role: str | None = None,
                      preferTags: str | None = None, obtainedCredits: int | None = None):
    return await get_data_by_query(mongo_db["users"], **locals())


@app.get("/article")
async def get_article_by(background_tasks: BackgroundTasks, id: int | None = None, aid: int | None = None,
                         timestamp: str | None = None, title: str | None = None, category: str | None = None,
                         language: str | None = None):
    rows = await get_data_by_query(mongo_db["articles"], **locals())
    return process_articles_response(rows)


@app.get("/reads")
async def get_read_by(background_tasks: BackgroundTasks, title: int | None = None,
                      name: str | None = None, region: str | None = None, category: str | None = None, ):
    return await get_data_by_query(mongo_db["reads"], **locals())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=UVICORN_HOST, port=UVICORN_PORT)
