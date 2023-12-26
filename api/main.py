import json
import os
from contextlib import asynccontextmanager

import redis
from fastapi import BackgroundTasks, FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
import boto3
from redis import Redis

UVICORN_HOST = os.environ.get("UVICORN_HOST", "127.0.0.1")
UVICORN_PORT = os.environ.get("UVICORN_PORT", 8000)

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")

REDIS_MASTER_URL = os.environ.get("REDIS_MASTER_URL", "redis://localhost:6379")
REDIS_REPLICA_URL = os.environ.get("REDIS_REPLICA_URL", "redis://localhost:6379")

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "media")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "root")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "root")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "database")
MONGODB_COLLECTION_NAME = os.environ.get("MONGODB_COLLECTION_NAME", "your_collection")

# Initialize MongoDB client
mongo_client = AsyncIOMotorClient(MONGODB_URL)
mongo_db = mongo_client[MONGODB_DB_NAME]

# Initialize Redis client with a master and replica
redis_master: Redis = redis.Redis.from_url(REDIS_MASTER_URL, db=0)
redis_replica: Redis = redis.Redis.from_url(REDIS_REPLICA_URL, db=0)

# Initialize S3 client from S3 bucket name and URL
s3 = boto3.resource('s3',
                    endpoint_url='https://localhost:9000',
                    aws_access_key_id=S3_ACCESS_KEY_ID,
                    aws_secret_access_key=S3_SECRET_ACCESS_KEY)


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
    print(s3.buckets.all())
    yield
    redis_master.close()
    redis_replica.close()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


async def set_cache(data, key: str):
    await redis_master.set(
        key,
        json.dumps(data),
        ex=120,
    )


async def get_cache(key: str):
    result = await redis_replica.get(key)
    if not result:
        return None

    return json.loads(result)

def parse_output(output):
    for r in output:
        r["id"] = str(r.pop("_id"))
    return output

def build_chache_key(collection,skip,limit,query):
    cache_components = {
        'collection': collection.name,  # assuming collection has a 'name' attribute
        'skip': skip,
        'limit': limit,
        'query': query,
    }
    
    cache_key = json.dumps(cache_components, sort_keys=True)
    return cache_key

async def get_data(background_tasks: BackgroundTasks, collection, skip: int = 0, limit: int = 10, query: dict = {}):
    cache_key = build_chache_key(collection,skip,limit,query)

    cached = await get_cache(cache_key)
    if cached:
        return cached

    result = await collection.find(query).skip(skip).limit(limit).to_list(limit)

    background_tasks.add_task(set_cache, result, cache_key)

    return parse_output(result)

async def get_data_by_query(background_tasks,collection, **kwargs):
    # Exclude specific variables from the query parameters
    query = {k: v for k, v in kwargs.items() if v is not None and 'collection' not in k.lower() }

    # Fetch data using the common get_data function
    return await get_data(background_tasks=background_tasks, collection=collection, query=query)

    
@app.get("/users")
async def get_users(background_tasks: BackgroundTasks, region:str | None ):
    users_collection = mongo_db["users"]
    return await get_data_by_query(collection=users_collection, ** locals())

@app.get("/articles")
async def get_articles(background_tasks: BackgroundTasks, skip: int = 0, limit: int = 10):
    articles_collection = mongo_db["articles"]
    return await get_data(background_tasks, articles_collection, skip, limit)

@app.get("/user")
async def get_user_by(background_tasks: BackgroundTasks, id: int | None = None, uid: int | None = None,
                    name: str | None = None, gender: str | None = None, email: str | None = None,
                    phone: str | None = None, dept: str | None = None, grade: str | None = None,
                    language: str | None = None, region: str | None = None, role: str | None = None,
                    preferTags: str | None = None, obtainedCredits: int | None = None):
    user_collection = mongo_db["users"]
    return await get_data_by_query(collection=user_collection,**locals())

@app.get("/article")
async def get_article_by(background_tasks: BackgroundTasks, id: int | None = None, aid: int | None = None,
                    timestamp:str | None= None,title: str | None = None, category: str | None = None, 
                    language: str | None = None):
    articles_collection = mongo_db["articles"]
    return await get_data_by_query(collection=articles_collection,**locals())

@app.get("/reads")
async def get_read_by(background_tasks: BackgroundTasks, title: int | None = None,
                      name: str | None = None,region:str | None= None, category:str | None= None,):
    reads_collection = mongo_db["reads"]
    return await get_data_by_query(collection=reads_collection,**locals())
                                   

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=UVICORN_HOST, port=UVICORN_PORT)
