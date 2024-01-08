# Build API

```shell
eval $(minikube -p minikube docker-env)
docker build -t api .
```

# Install API

```shell
kubectl create namespace api
helm upgrade --install --wait -n api --values chart/values.yaml api chart
```
