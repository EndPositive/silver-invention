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
minikube addons enable ingress
minikube addons enable ingress-dns
minikube tunnel
```

See minikube ingress DNS on how to setup local DNS to access services in cluster without port-forwarding: https://minikube.sigs.k8s.io/docs/handbook/addons/ingress-dns/

Each of the following directories contain a README.md with instructions on how to install the components. Install in the following order:
1. Monitoring (`./monitoring`)
2. Storage (`./s3`)
3. Storage initialization (`./s3-seed`)
4. Database (`./database`)
5. Caching (`cache`)
6. API (`./api`)
