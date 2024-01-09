import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import boto3
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis
from starlette.responses import Response

from redis_replica_backend import RedisReplicaBackend

UVICORN_HOST = os.environ.get("UVICORN_HOST", "127.0.0.1")
UVICORN_PORT = os.environ.get("UVICORN_PORT", 8000)

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://root:root@localhost:27017")

REDIS_MASTER_URL = os.environ.get("REDIS_MASTER_URL", "redis://@localhost:6379/0")
REDIS_REPLICA_URL = os.environ.get("REDIS_REPLICA_URL", "redis://@localhost:6379/0")

S3_INTERNAL_ENDPOINT_URL = os.environ.get("S3_INTERNAL_ENDPOINT_URL", "http://localhost:9000")
S3_EXTERNAL_ENDPOINT_URL = os.environ.get("S3_EXTERNAL_ENDPOINT_URL", "http://localhost:9000")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "media")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "PASSWORD")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "USERNAME")

MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "database")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB client
    global mongo_db
    print("waiting for mongodb connection...")
    mongo_client = AsyncIOMotorClient(MONGODB_URL)
    mongo_db = mongo_client[MONGODB_DB_NAME]
    print(await mongo_client.server_info())

    # Initialize Redis client with a master and replica
    print("waiting for redis connection...")
    redis_master = aioredis.from_url(REDIS_MASTER_URL)
    redis_replica = aioredis.from_url(REDIS_REPLICA_URL)
    FastAPICache.init(RedisReplicaBackend(redis_master, redis_replica))
    print("waiting for redis master connection...")
    print(await redis_master.ping())
    print("waiting for redis replica connection...")
    print(await redis_replica.ping())

    # Initialize S3 client from S3 bucket name and URL
    global s3
    print("waiting for s3 connection...")
    s3 = boto3.client(
        's3',
        endpoint_url=S3_INTERNAL_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY,
        config=boto3.session.Config(signature_version='s3v4', region_name='us-east-1')
    )
    # test if s3 is connected
    print(s3.list_buckets())
    yield
    await redis_master.close()
    await redis_replica.close()


# Initialize FastAPI app
app = FastAPI(lifespan=lifespan)


# probes
@app.get("/liveness", include_in_schema=False)
async def readiness_probe():
    # return empty HTTP response with 200
    return Response()


def parse_output(output):
    for r in output:
        if "_id" in r:
            r["id"] = str(r.pop("_id"))
    return output


async def get_data(collection, skip: int = 0, limit: int = 10, query: dict = {}) -> (
        dict, bool):
    result = await collection.find(query).skip(skip).limit(limit).to_list(limit)

    for row in result:
        if "period" in row:
            del row["period"]

    return result


async def get_data_by_query(collection, skip, limit, **kwargs) -> (dict, bool):
    # Exclude specific variables from the query parameters
    query = {k: v for k, v in sorted(kwargs.items()) if v is not None}

    # Fetch data using the common get_data function
    return await get_data(collection=collection, query=query, skip=skip, limit=limit)


def join_collections(pipeline, from_collection, local_field, foreign_field, as_field):
    pipeline.append({
        "$lookup": {
            "from": from_collection,
            "localField": local_field,
            "foreignField": foreign_field,
            "as": as_field
        }
    })


async def aggregate_pipeline(collection, pipeline, project_fields, skip, limit):
    stages = [
        {"$skip": skip},
        {"$limit": limit}
    ]
    if (len(project_fields) > 1):
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
            ).replace(S3_INTERNAL_ENDPOINT_URL, S3_EXTERNAL_ENDPOINT_URL)
            for image_file_name in row["image"].split(",") if image_file_name
        ]

        if row["video"]:
            row["video"] = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": S3_BUCKET_NAME,
                    "Key": row["video"]
                }
            ).replace(S3_INTERNAL_ENDPOINT_URL, S3_EXTERNAL_ENDPOINT_URL)

    return rows


@app.get("/", include_in_schema=False)
async def docs_redirect():
    return RedirectResponse(url='/docs')


@app.get("/users")
@cache(expire=60)
async def get_user_by(id: str = None, uid: int = None,
                      name: str = None, gender: str = None, email: str = None,
                      phone: str = None, dept: str = None, grade: str = None,
                      language: str = None, region: str = None, role: str = None,
                      preferTags: str = None, obtainedCredits: int = None, skip: int = 0, limit: int = 10):
    rows = await get_data_by_query(mongo_db["users"], **locals())
    return JSONResponse(content=parse_output(rows))


@app.get("/articles")
@cache(expire=60)
async def get_article_by(id: str = None, aid: int = None,
                         timestamp: str = None, title: str = None, category: str = None,
                         language: str = None, skip: int = 0, limit: int = 10):
    rows = await get_data_by_query(mongo_db["articles"], **locals())

    return JSONResponse(content=process_articles_response(parse_output(rows)))


async def get_reads_collection(collection, params):
    reads_collection = collection
    pipeline = [{"$match": {}}]

    if "region" in params and params["region"]:
        pipeline[0]["$match"]["region"] = params["region"]

    if "category" in params and params["category"]:
        pipeline[0]["$match"]["category"] = params["category"]

    return reads_collection, pipeline


@app.get("/be-read")
@cache(expire=60)
async def get_be_read_by(aid: int = None, category: str = None,
                         skip: int = 0, limit: int = 10):
    bereads_collection, pipeline = await get_reads_collection(mongo_db["beReads"], locals())

    project_fields = {
        "readNum": 1,
        "commentNum": 1,
        "agreeNum": 1,
        "shareNum": 1
    }

    join_collections(pipeline, "articles", "aid", "aid", "article")
    project_fields["article.id"] = 1
    project_fields["article.title"] = 1
    project_fields["article.category"] = 1
    project_fields["article.abstract"] = 1
    project_fields["article.articleTags"] = 1
    project_fields["article.authors"] = 1
    project_fields["article.language"] = 1
    project_fields["article.text"] = 1
    project_fields["article.image"] = 1
    project_fields["article.video"] = 1
    pipeline.append({"$unwind": {"path": "$article"}})

    rows = await aggregate_pipeline(bereads_collection, pipeline, project_fields, skip, limit)

    for row in rows:
        row["article"] = process_articles_response(parse_output([row["article"]]))[0]

    return JSONResponse(content=rows)


@app.get("/popular")
@cache(expire=60)
async def get_popular(temporalGranularity: str = None, timestamp: int = 1506988800000):
    popular = await get_data_by_query(mongo_db["popular_rank"], skip=0, limit=5, **locals())
    articleIds = popular[0]['articleAidList'][:5]
    query = {"aid": {"$in": articleIds}}
    rows = await get_data(mongo_db["articles"], query=query)
    return JSONResponse(content=process_articles_response(parse_output(rows)))


@app.get("/reads")
@cache(expire=60)
async def get_read_by(user_id: str = None, skip: int = 0, limit: int = 10):
    reads_collection, pipeline = await get_reads_collection(mongo_db["reads"], locals())

    project_fields = {}

    join_collections(pipeline, "users", "uid", "uid", "user")
    project_fields["user.id"] = 1
    project_fields["user.name"] = 1
    project_fields["user.gender"] = 1
    project_fields["user.email"] = 1
    project_fields["user.phone"] = 1
    project_fields["user.grade"] = 1
    project_fields["user.language"] = 1
    project_fields["user.role"] = 1
    project_fields["user.preferTags"] = 1
    project_fields["user.obtainedCredits"] = 1
    pipeline.append({"$unwind": {"path": "$user"}})
    if user_id:
        pipeline.append({"$match": {"user.id": user_id}})

    join_collections(pipeline, "articles", "aid", "aid", "article")
    project_fields["article.id"] = 1
    project_fields["article.title"] = 1
    project_fields["article.category"] = 1
    project_fields["article.abstract"] = 1
    project_fields["article.articleTags"] = 1
    project_fields["article.authors"] = 1
    project_fields["article.language"] = 1
    project_fields["article.text"] = 1
    project_fields["article.image"] = 1
    project_fields["article.video"] = 1
    pipeline.append({"$unwind": {"path": "$article"}})

    project_fields = {"_id": 0, "readTimeLength": 1, "agreeOrNot": 1, "commentOrNot": 1, "shareOrNot": 1,
                      **project_fields}

    rows = await aggregate_pipeline(reads_collection, pipeline, project_fields, skip, limit)

    for row in rows:
        row["article"] = process_articles_response(parse_output([row["article"]]))[0]

    return JSONResponse(content=rows)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=UVICORN_HOST, port=int(UVICORN_PORT))
