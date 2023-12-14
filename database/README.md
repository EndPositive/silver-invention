# Install MongoDB

```shell
kubectl create namespace mongodb
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install -n mongodb --values values.yaml mongodb bitnami/mongodb-sharded --version 7.1.6
```
