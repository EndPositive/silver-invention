## Cluster setup

```shell
sh ./initiate.sh

kubectl get pods

kubectl exec -it mongo-router-X -- mongosh

db.getSiblingDB("admin").auth("admin","1234")

sh.status()
```