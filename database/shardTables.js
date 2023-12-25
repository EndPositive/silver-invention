import { 
  DB,
  SHARD1KEY,
  SHARD2KEY,
  SHARD1TAG,
  SHARD2TAG,
  USERS,
  ARTICLES,
  ARTICLES_SCIENCE,
  READS,BE_READS,
  BE_READS_SCIENCE,
  POPULAR_RANK } from "./config"

sh.addShardTag(SHARD1KEY, SHARD1TAG);
sh.addShardTag(SHARD2KEY, SHARD2TAG);

const computeMaterializedView = (fromTable,key,value,outTable) => {
  db[fromTable].aggregate([
    {
      $match:{[key]: value}
    },
    {
      $out: outTable
    },
  ])
}

const computeReadsRegion = () => {
  db.users.createIndex({ uid: 1 });
  db.reads.createIndex({ uid: 1 });

  db.reads.aggregate([
    {
      $lookup:{
          from: users,
          localField: "uid",
          foreignField: "uid",
          as: "user",
        },
    },
    {
      $project:{
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
      $merge:reads,
    },
  ])
}

const computePopularRank = () => {
const granularity = ["day", "week","month"];

granularity.forEach(temporalGranularity => {
  // Use the $dateTrunc operator to truncate the timestamp field of the be-read table according to the temporal granularity value.
  // This will create a new field that represents the start of the period for each document.
  db.beRead.aggregate([
    {
      $set: {
        period: {
          $dateTrunc: {
            date: "$timestamp",
            unit: temporalGranularity
          }
        }
      }
    },
    // Group the documents by the period field, and calculate the weighted interaction counts for each group.
    // For example, assign different weights to readNum, commentNum, agreeNum, and shareNum.
    // Also, use the $first accumulator to get the first article id for each period, and use the $push accumulator to append all the article ids to an array for each period.
    {
      $group: {
        _id: "$period",
        readCount: {$sum: "$readNum"},
        commentCount: {$sum: "$commentNum"},
        agreeCount: {$sum: "$agreeNum"},
        shareCount: {$sum: "$shareNum"},
        totalInteractions: {
          $sum: {
            $add: [
              "$readNum",
              {$multiply: ["$commentNum", 2]},
              {$multiply: ["$agreeNum", 3]},
              {$multiply: ["$shareNum", 4]}
            ]
          }
        },
        aid: {$first: "$aid"}, // the first article id for each period
        articleAidList: {$push: "$aid"} // the array of article ids for each period
      }
    },
    // Sort the documents by the period field and the totalInteractions field in descending order.
    {
      $sort: {
        "_id": 1,
        "totalInteractions": -1
      }
    },
    // Use the $project stage to reshape the output document and extract the relevant fields for the popular rank table.
    {
      $project: {
        _id: 0,
        timestamp: "$_id",
        temporalGranularity: temporalGranularity,
        articleAidList: 1 // the array of article ids for each period
      }
    },
    // Use the $merge stage to write the output to the popularRank collection, inserting new documents or replacing existing ones based on the _id.
    {
      $merge: {
        into: "popular_rank",
        on: ["timestamp", "temporalGranularity"],
        whenMatched: "replace",
        whenNotMatched: "insert"
      }
    }
  ])
})

}

function changeLastLetter(str) {
    // Ensure the input is a non-empty string
    if (typeof str !== 'string' || str.length === 0) {
        return "Invalid input";
    }

    // Get the last letter of the string
    const lastLetter = str.slice(-1);

    // Check if the last letter is a lowercase letter
    if (/[a-z]/i.test(lastLetter)) {
        // Use String.fromCharCode to get the next letter in the alphabet
        const nextLetter = String.fromCharCode(lastLetter.charCodeAt(0) + 1);

        // Replace the last letter in the string with the next letter
        return str.slice(0, -1) + nextLetter;
    } else {
        // If the last letter is not a lowercase letter, return an error message
        return "Last character is not a letter";
    }
}

const shardByKey = ({table,shardKey,shardValues}) => {
    sh.enableSharding(table);

    db[table].createIndex({ [shardKey]: 1 });

    shardValues.forEach(({ shard, value }) => {
        sh.addTagRange(`${DB}.${table}`, { [shardKey]: value }, { [shardKey]: changeLastLetter(value) }, shard);
    });

    sh.shardCollection(`${DB}.${table}`, { [shardKey]: 1 });

    // wait forever for the chunks to be distributed
    db[table].getShardDistribution(); // verify chunks distributed on shards
}

const shardByRegion = (table, shardValues) => {
    shardByKey({
        table,
        shardKey: "region",
        shardValues,
    });
};

const shardByCategory = (table, shardValues) => {
    shardByKey({
        table,
        shardKey: "category",
        shardValues,
    });
};

computeMaterializedView(ARTICLES,"category","science",ARTICLES_SCIENCE);
computeMaterializedView(BE_READS,"category","science",BE_READS_SCIENCE);

computeReadsRegion();

shardByRegion(USERS, [
    { shard: SHARD1, value: "Beijing" },
    { shard: SHARD2, value: "Hong Kong" },
]);

shardByRegion(READS, [
    { shard: SHARD1, value: "Beijing" },
    { shard: SHARD2, value: "Hong Kong" },
]);

shardByCategory(ARTICLES, [
    { shard: SHARD1, value: "science" },
    { shard: SHARD2, value: "technology" },
]);

shardByCategory(ARTICLES_SCIENCE, [
    { shard: SHARD1, value: "science" },
]);

shardByCategory(BE_READS, [
    { shard: SHARD1, value: "science" },
    { shard: SHARD2, value: "technology" },
]);

shardByCategory(BE_READS_SCIENCE, [
    { shard: SHARD2, value: "technology" },
]);

shardByKey({
    table: POPULAR_RANK,
    shardKey: "temporalGranularity",
    shardValues: [
        { shard: SHARD1, value: "daily" },
        { shard: SHARD2, value: "weekly" },
        { shard: SHARD2, value: "monthly" },
    ],
});