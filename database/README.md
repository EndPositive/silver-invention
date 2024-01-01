# Install MongoDB

```shell
kubectl create namespace mongodb
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install -n mongodb --values values.yaml mongodb bitnami/mongodb-sharded --version 7.1.6
```

```shell
mongoimport -h localhost:27017 -u root -p root --authenticationDatabase=admin --db database --collection users --file user.dat
mongoimport -h localhost:27017 -u root -p root --authenticationDatabase=admin --db database --collection reads --file read.dat
mongoimport -h localhost:27017 -u root -p root --authenticationDatabase=admin --db database --collection articles --file article.dat
mongosh mongodb://root:root@localhost:27017/ createTables.js shardTables.js
```
