FROM python:3.11-alpine

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
