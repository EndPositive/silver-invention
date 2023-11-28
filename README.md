## Minikube setup

```shell
minikube start --kubernetes-version=v1.23 \
  --memory=16g \
  --cpus=8 \
  --bootstrapper=kubeadm \
  --extra-config=kubelet.authentication-token-webhook=true \
  --extra-config=kubelet.authorization-mode=Webhook \
  --extra-config=scheduler.bind-address=0.0.0.0 \
  --extra-config=controller-manager.bind-address=0.0.0.0 \
  --image-mirror-country=cn
minikube addons disable metrics-server
```