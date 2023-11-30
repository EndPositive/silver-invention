#!/bin/bash

echo -e "Deleting config nodes"
kubectl delete -f  mongodb-nodeport-svc.yaml &
kubectl delete deployment mongo-router
kubectl delete statefulsets mongo-shard1
kubectl delete services mongo-shard1-service
kubectl delete statefulsets mongo-shard2
kubectl delete services mongo-shard2-service
kubectl delete statefulsets mongo-shard3
kubectl delete services mongo-shard3-service
kubectl delete statefulsets mongo-configdb
kubectl delete services mongo-configdb-service
kubectl delete secret shared-bootstrap-data
kubectl delete pvc --all

rm ./mongodb-shard-1.yaml
rm ./mongodb-shard-2.yaml
rm ./mongodb-shard-3.yaml
exit
