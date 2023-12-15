# Install MongoDB

```shell
kubectl create namespace mongodb
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install -n mongodb --values values.yaml mongodb bitnami/mongodb-sharded --version 7.1.6
```

```javascript
db.stats(); // verify shards available
sh.addShardTag('mongodb-mongodb-sharded-shard-0', 'DBMS1');
sh.addShardTag('mongodb-mongodb-sharded-shard-1', 'DBMS2');
sh.addTagRange("database.users", {region: "Beijing"}, {region: "Beijinh"}, "DBMS1");
sh.addTagRange("database.users", {region: "Hong Kong"}, {region: "Hong Konh"}, "DBMS2");
sh.enableSharding("users");
db.users.createIndex({ region: 1 });
sh.shardCollection("database.users", { region: 1 });
// wait forever for the chunks to be distributed
db.users.getShardDistribution(); // verify chunks distributed on shards
sh.status(); // to view chunk setup
```
