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