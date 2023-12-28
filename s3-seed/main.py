import os

import boto3

S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "media")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "PASSWORD")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "USERNAME")

# Initialize S3 client from S3 bucket name and URL
s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
    config=boto3.session.Config(signature_version='s3v4', region_name='us-east-1')
)


def main():
    print("waiting for s3 connection...")
    print(s3.list_buckets())

    for root, dirs, files in os.walk("../db-generation/articles"):
        for file in files:
            # construct the full local path
            local_path = os.path.join(root, file)

            # upload the file, if it already exists, ignore it
            try:
                s3.upload_file(local_path, S3_BUCKET_NAME, file)
            except Exception as e:
                print(e)


if __name__ == "__main__":
    main()
