# Install Prometheus

```shell
kubectl create -f kube-prometheus/manifests/setup
kubectl wait \
	--for condition=Established \
	--all CustomResourceDefinition \
	--namespace=monitoring
kubectl create -f kube-prometheus/manifests/
```

# Access

```shell
kubectl --namespace monitoring port-forward svc/prometheus-k8s 9090
kubectl --namespace monitoring port-forward svc/alertmanager-main 9093
kubectl --namespace monitoring port-forward svc/grafana 3000
# admin/admin
```

# Uninstall

```shell
kubectl delete --ignore-not-found=true -f kube-prometheus/manifests/ -f kube-prometheus/manifests/setup
```
