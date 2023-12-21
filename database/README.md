# Install MongoDB

```shell
kubectl create namespace mongodb
helm repo add bitnami https://charts.bitnami.com/bitnami
helm upgrade --install -n mongodb --values values.yaml mongodb bitnami/mongodb-sharded --version 7.1.6
```

```javascript
db.stats(); // verify shards available

// Tag Shards 
sh.addShardTag('mongodb-mongodb-sharded-shard-0', 'DBMS1');
sh.addShardTag('mongodb-mongodb-sharded-shard-1', 'DBMS2');

// Shard users
sh.addTagRange("database.users", {region: "Beijing"}, {region: "Beijinh"}, "DBMS1");
sh.addTagRange("database.users", {region: "Hong Kong"}, {region: "Hong Konh"}, "DBMS2");
sh.enableSharding("users");
db.users.createIndex({ region: 1 });
sh.shardCollection("database.users", { region: 1 });

// wait forever for the chunks to be distributed
db.users.getShardDistribution(); // verify chunks distributed on shards

// Shard articles
sh.addTagRange("database.articles", {category: "technology"}, {region: "technologz"}, "DBMS1");
sh.addTagRange("database.articles", {category: "science"}, {region: "sciencf"}, "DBMS2");
sh.enableSharding("articles");
db.articles.createIndex({ category: 1 });
// Create Materialized View for Science Articles 
db.articles.aggregate([
  {
    $match:
      /**
       * query: The query in MQL.
       */
      {
        category: "science",
      },
  },
  {
    $out:
      /**
       * Provide the name of the output collection.
       */
      "articles_science",
  },
])
sh.addTagRange("database.articles_science", {category: "science"}, {region: "sciencf"}, "DBMS2");
sh.enableSharding("articles_science");
db.articles_science.createIndex({ category: 1 });

db.articles.getShardDistribution(); // verify chunks distributed on shards
db.articles_science.getShardDistribution(); // verify chunks distributed on shards

// Modify Reads table to include region

db.users.createIndex({ uid: 1 });
db.reads.createIndex({ uid: 1 });

db.reads.aggregate([
  {
    $lookup:
      /**
       * from: The target collection.
       * localField: The local join field.
       * foreignField: The target join field.
       * as: The name for the results.
       * pipeline: Optional pipeline to run on the foreign collection.
       * let: Optional variables to use in the pipeline field stages.
       */
      {
        from: "users",
        localField: "uid",
        foreignField: "uid",
        as: "user",
      },
  },
  {
    $project:
      /**
       * specifications: The fields to
       *   include or exclude.
       */
      {
        _id: 1,
        timestamp: 1,
        id: 1,
        uid: 1,
        aid: 1,
        readTimeLength: 1,
        agreeOrNot: 1,
        commentOrNot: 1,
        shareOrNot: 1,
        commentDetail: 1,
        region: {
          $getField: {
            field: "region",
            input: {
              $arrayElemAt: ["$user", 0],
            },
          },
        },
      },
  },
  {
    $merge:
      /**
       * Provide the name of the output collection.
       */
      "reads",
  },
])

// Shard reads
sh.addTagRange("database.reads", {region: "Beijing"}, {region: "Beijinh"}, "DBMS1");
sh.addTagRange("database.reads", {region: "Hong Kong"}, {region: "Hong Konh"}, "DBMS2");
sh.enableSharding("reads");
db.reads.createIndex({ region: 1 });
sh.shardCollection("database.reads", { region: 1 });

// wait forever for the chunks to be distributed
db.reads.getShardDistribution(); // verify chunks distributed on shards


sh.status(); // to view chunk setup
```
