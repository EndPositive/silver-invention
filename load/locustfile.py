import random

from locust import HttpUser, task


class DBMSAPIUser(HttpUser):
    @task
    def users(self):
        user_id = random.randint(1, 9999)
        self.client.get(f"/users?id=u{user_id}")

    @task
    def articles(self):
        article_id = random.randint(1, 9999)
        self.client.get(f"/articles?id=a{article_id}")

    @task
    def beread(self):
        article_id = random.randint(1, 9999)
        self.client.get(f"/be-read?aid={article_id}")
