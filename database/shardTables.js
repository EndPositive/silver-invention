const DB = "database",
    SHARD1TAG = "DBMS1",
    SHARD2TAG = "DBMS2",
    SHARD1KEY = 'mongodb-mongodb-sharded-shard-0',
    SHARD2KEY = 'mongodb-mongodb-sharded-shard-1',
    USERS = "users",
    ARTICLES = "articles",
    ARTICLES_SCIENCE = "articles_science",
    READS = "reads",
    BE_READS = "beReads",
    BE_READS_SCIENCE = "be_reads_science",
    POPULAR_RANK = "popular_rank";

db = db.getSiblingDB('database');

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

const shardByKey = ({table, shardKey, shardValues}) => {
    sh.enableSharding(table);

    db[table].createIndex({[shardKey]: 1});

    shardValues.forEach(({tag, value}) => {
        sh.addTagRange(`${DB}.${table}`, {[shardKey]: value}, {[shardKey]: changeLastLetter(value)}, tag);
    });

    sh.shardCollection(`${DB}.${table}`, {[shardKey]: 1});

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
    {tag: SHARD1TAG, value: "Beijing"},
    {tag: SHARD2TAG, value: "Hong Kong"},
]);

shardByRegion(READS, [
    {tag: SHARD1TAG, value: "Beijing"},
    {tag: SHARD2TAG, value: "Hong Kong"},
]);

shardByCategory(ARTICLES, [
    {tag: SHARD1TAG, value: "science"},
    {tag: SHARD2TAG, value: "technology"},
]);

shardByCategory(ARTICLES_SCIENCE, [
    {tag: SHARD1TAG, value: "science"},
]);

shardByCategory(BE_READS, [
    {tag: SHARD1TAG, value: "science"},
    {tag: SHARD2TAG, value: "technology"},
]);

shardByCategory(BE_READS_SCIENCE, [
    {tag: SHARD2TAG, value: "technology"},
]);

shardByKey({
    table: POPULAR_RANK,
    shardKey: "temporalGranularity",
    shardValues: [
        {tag: SHARD1TAG, value: "daily"},
        {tag: SHARD2TAG, value: "weekly"},
        {tag: SHARD2TAG, value: "monthly"},
    ],
});