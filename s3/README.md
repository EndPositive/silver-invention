# Install Minio

```shell
kubectl create namespace minio
helm repo add minio https://charts.min.io/
helm upgrade --install -n minio --values values.yaml minio minio/minio
```
