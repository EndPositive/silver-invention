# Install MongoDB

```shell
kubectl create namespace cache
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install -n cache --values values.yaml redis bitnami/redis --version 18.5.0
```
