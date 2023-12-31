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

    return result


async def get_data_by_query(collection, background_tasks: BackgroundTasks, **kwargs):
    # Exclude specific variables from the query parameters
    query = {k: v for k, v in sorted(kwargs.items()) if v is not None}

    # Fetch data using the common get_data function
    return await get_data(background_tasks=background_tasks, collection=collection, query=query)

async def join_collections(pipeline, from_collection, local_field, foreign_field, as_field):
    pipeline.append({
        "$lookup": {
            "from": from_collection,
            "localField": local_field,
            "foreignField": foreign_field,
            "as": as_field
        }
    })

async def aggregate_pipeline(collection, pipeline, project_fields, skip, limit):
    stages=[
        {"$skip": skip},
        {"$limit": limit}
    ]
    if(len(project_fields)>1):
        stages.append({"$project": project_fields})

    pipeline.extend(stages)

    result_cursor = collection.aggregate(pipeline)
    return await result_cursor.to_list(limit)

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
async def get_users(background_tasks: BackgroundTasks, region: str):
    result = await get_data_by_query(mongo_db["users"], **locals())
    return parse_output(result)


@app.get("/articles")
async def get_articles(background_tasks: BackgroundTasks, skip: int = 0, limit: int = 10):
    rows = await get_data(background_tasks, mongo_db["articles"], skip, limit)
    return process_articles_response(parse_output(rows))


@app.get("/user")
async def get_user_by(background_tasks: BackgroundTasks, id: int = None, uid: int = None,
                      name: str = None, gender: str = None, email: str = None,
                      phone: str = None, dept: str = None, grade: str = None,
                      language: str = None, region: str = None, role: str = None,
                      preferTags: str = None, obtainedCredits: int = None):
    result = await get_data_by_query(mongo_db["users"], **locals())
    return parse_output(result)

@app.get("/article")
async def get_article_by(background_tasks: BackgroundTasks, id: int = None, aid: int = None,
                         timestamp: str = None, title: str = None, category: str = None,
                         language: str = None):
    rows = await get_data_by_query(mongo_db["articles"], **locals())
    return process_articles_response(parse_output(rows))

async def get_reads_collection(collection, params):
    reads_collection = collection
    pipeline = [{"$match": {}}]

    if "region" in params and params["region"]:
        pipeline[0]["$match"]["region"] = params["region"]

    if "category" in params and params["category"]:
        pipeline[0]["$match"]["category"] = params["category"]

    return reads_collection, pipeline

@app.get("/be-read")
async def get_article_by(background_tasks: BackgroundTasks,
                        aid: int = None, category: str = None,
                        skip: int = 0, limit: int = 10):
    params = locals()

    bereads_collection, pipeline = await get_reads_collection(mongo_db["be-read"],params)
    
    project_fields = {
        "readNum":1,
        "commentNum":1,
        "agreeNum":1,
        "shareNum":1
    }

    if aid:
        await join_collections(pipeline, "articles", "aid", "aid", "article")
        project_fields["title"] = "$article.title"
        project_fields["abstract"] = "$article.abstract"
        project_fields["text"] = "$article.text"
        project_fields["image"] = "$article.image"
        project_fields["video"] = "$article.video"
        pipeline.append({"$unwind": {"path": "$article"}})

    rows = await aggregate_pipeline(bereads_collection,pipeline,project_fields,skip,limit)
    return process_articles_response(parse_output(rows))


@app.get("/reads")
async def get_read_by(background_tasks: BackgroundTasks,
                      region: str = None, category: str = None,
                      email: str = None, title: str = None,
                      skip: int = 0, limit: int = 10):
    params = locals()

    reads_collection, pipeline = await get_reads_collection(mongo_db["reads"],params)

    project_fields = {}

    if email:
        await join_collections(pipeline, "users", "uid", "uid", "user")
        project_fields["user.name"] = 1
        project_fields["user.email"] = 1
        pipeline.append({"$unwind": {"path": "$user"}})
        pipeline.append({"$match": {"user.email": email}})

    if title:
        await join_collections(pipeline, "articles", "aid", "aid", "article")
        project_fields["article.title"] = 1
        project_fields["article.abstract"] = 1
        pipeline.append({"$unwind": {"path": "$article"}})
        pipeline.append({"$match": {"article.title": title}})

    project_fields = {"_id": 0, "readTimeLength": 1, "agreeOrNot": 1, "commentOrNot": 1, "shareOrNot": 1, **project_fields}
    
    return await aggregate_pipeline(reads_collection,pipeline,project_fields,skip,limit)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8088)
