#!/bin/bash

# Creating secret
TMPFILE=$(mktemp)
/usr/bin/openssl rand -base64 741 > $TMPFILE
kubectl create secret generic shared-bootstrap-data --from-file=internal-auth-mongodb-keyfile=$TMPFILE
rm $TMPFILE

# Creating config nodes
kubectl create -f  mongodb-config.yaml

# Create each MongoDB Shard Service using a Kubernetes StatefulSet
echo "Creating StatefulSet & Service for each MongoDB Shard Replica Set"
sed -e 's/shardX/shard1/g; s/ShardX/Shard1/g' mongodb-shard.yaml > mongodb-shard-1.yaml
kubectl create -f mongodb-shard-1.yaml
sed -e 's/shardX/shard2/g; s/ShardX/Shard2/g' mongodb-shard.yaml > mongodb-shard-2.yaml
kubectl create -f mongodb-shard-2.yaml
sed -e 's/shardX/shard3/g; s/ShardX/Shard3/g' mongodb-shard.yaml > mongodb-shard-3.yaml
kubectl create -f mongodb-shard-3.yaml


# Creating router nodes
kubectl create -f  mongodb-router.yaml
# Expose router nodes
kubectl create -f  mongodb-nodeport-svc.yaml

echo
echo "Waiting for all the shards and configdb containers to come up (`date`)..."
echo " (IGNORE any reported not found & connection errors)"
sleep 30
echo -n "  "
# TODO: investigate sometimes the configdb-2 is not found - 
# find a better way to check if node is up
until kubectl exec -it mongo-configdb-2 -- mongosh --quiet --eval 'db.getMongo()'; do
    sleep 5
    echo -n "  "
done
echo -n "  "
until kubectl exec -it mongo-shard1-0 -- mongosh --quiet --eval 'db.getMongo()'; do
    sleep 5
    echo -n "  "
done
echo -n "  "
until kubectl exec -it mongo-shard2-0 -- mongosh --quiet --eval 'db.getMongo()'; do
    sleep 5
    echo -n "  "
done
echo -n "  "
until kubectl exec -it mongo-shard3-0 -- mongosh --quiet --eval 'db.getMongo()'; do
    sleep 5
    echo -n "  "
done
echo "...shards & config containers are now running (`date`)"
echo

# Initialise the Config Server Replica Set and each Shard Replica Set
# TODO: find a better way to iterate through all shards - kubectl get pods | grep shard
echo "Configuring Config Server's & each Shard's Replica Sets"
kubectl exec -it mongo-configdb-0 -- mongosh --eval 'rs.initiate({_id: "rs-config-server", version: 1, members: [ {_id: 0, host: "mongo-configdb-0.mongo-configdb-service.default.svc.cluster.local:27017"}, {_id: 1, host: "mongo-configdb-1.mongo-configdb-service.default.svc.cluster.local:27017"}, {_id: 2, host: "mongo-configdb-2.mongo-configdb-service.default.svc.cluster.local:27017"} ]});'
kubectl exec -it mongo-shard1-0 -- mongosh --eval 'rs.initiate({_id: "Shard1RepSet", version: 1, members: [ {_id: 0, host: "mongo-shard1-0.mongo-shard1-service.default.svc.cluster.local:27017"}]});'
kubectl exec -it mongo-shard2-0 -- mongosh --eval 'rs.initiate({_id: "Shard2RepSet", version: 1, members: [ {_id: 0, host: "mongo-shard2-0.mongo-shard2-service.default.svc.cluster.local:27017"}]});'
kubectl exec -it mongo-shard3-0 -- mongosh --eval 'rs.initiate({_id: "Shard3RepSet", version: 1, members: [ {_id: 0, host: "mongo-shard3-0.mongo-shard3-service.default.svc.cluster.local:27017"}]});'
echo


# Wait for each MongoDB Shard's Replica Set + the ConfigDB Replica Set to each have a primary ready
# TODO: find a better way to iterate through all shards - kubectl get pods | grep shard
echo "Waiting for all the MongoDB ConfigDB & Shards Replica Sets to initialise..."
kubectl exec -it mongo-configdb-0 -- mongosh --quiet --eval 'while (rs.status().hasOwnProperty("myState") && rs.status().myState != 1) { print("."); sleep(1000); };'
kubectl exec -it mongo-shard1-0 -- mongosh --quiet --eval 'while (rs.status().hasOwnProperty("myState") && rs.status().myState != 1) { print("."); sleep(1000); };'
kubectl exec -it mongo-shard2-0 -- mongosh --quiet --eval 'while (rs.status().hasOwnProperty("myState") && rs.status().myState != 1) { print("."); sleep(1000); };'
kubectl exec -it mongo-shard3-0 -- mongosh --quiet --eval 'while (rs.status().hasOwnProperty("myState") && rs.status().myState != 1) { print("."); sleep(1000); };'
sleep 2 # Just a little more sleep to ensure everything is ready!
echo "...initialisation of the MongoDB Replica Sets completed"
echo

for pod in $(kubectl get pods --template '{{range.items}}{{.metadata.name}}{{"\n"}}{{end}}'  | grep "mongo-router"); do
  echo "Configuring ConfigDB to be aware of the 3 Shards"
kubectl exec -it $pod -- mongosh --eval 'sh.addShard("Shard1RepSet/mongo-shard1-0.mongo-shard1-service.default.svc.cluster.local:27017");'
kubectl exec -it $pod -- mongosh --eval 'sh.addShard("Shard2RepSet/mongo-shard2-0.mongo-shard2-service.default.svc.cluster.local:27017");'
kubectl exec -it $pod -- mongosh --eval 'sh.addShard("Shard3RepSet/mongo-shard3-0.mongo-shard3-service.default.svc.cluster.local:27017");'
sleep 3
done

# Create the Admin User
echo "Creating user: 'admin'"
router=$(kubectl get pods --template '{{range.items}}{{.metadata.name}}{{"\n"}}{{end}}'  | grep "mongo-router" | head -1)
kubectl exec -it $router -- mongosh --eval 'db.getSiblingDB("admin").createUser({user:"admin",pwd:"'"1234"'",roles:[{role:"root",db:"admin"}]});'
echo

echo "Done"