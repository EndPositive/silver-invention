import {USERS, ARTICLES, ARTICLES_SCIENCE, READS, BE_READS, BE_READS_SCIENCE, POPULAR_RANK} from "./config"

const collections = db.listCollections().toArray();
const collectionExists = (collectionName) => collections.some(collection => collection.name === collectionName);

const COLLECTIONS = [USERS, ARTICLES, ARTICLES_SCIENCE, READS, BE_READS, BE_READS_SCIENCE, POPULAR_RANK]

COLLECTIONS.forEach(collection => {
    if (!collectionExists(collection)) {
        db.createCollection(collection)
    }
});

/**
 * Responsible for filtering out a table by a property and storing the reuslt in another table
 *
 * @param {*} fromTable The table from which the aggregation starts
 * @param {*} key The name of the property for which the filter is applied
 * @param {*} value The value of the property for which the filter is applied
 * @param {*} outTable The table where the result is stored
 */
const computeMaterializedView = (fromTable, key, value, outTable) => {
    db[fromTable].aggregate([
        {
            $match: {[key]: value}
        },
        {
            $out: outTable
        },
    ])
}

/**
 * Responsible for adding $region and $category fields into each read record
 * according to the article and the user
 *
 * The $region is used for sharding the table
 * The $category is needed for computing the BE-READS table
 */
const alternateReads = () => {
    db[USERS].createIndex({uid: 1});
    db[ARTICLES].createIndex({aid: 1});
    db[READS].createIndex({uid: 1});
    db[READS].createIndex({aid: 1});

    db[READS].aggregate([
        {
            $lookup: {
                from: USERS,
                localField: "uid",
                foreignField: "uid",
                as: "user",
            },
        },
        {
            $lookup: {
                from: ARTICLES,
                localField: "aid",
                foreignField: "aid",
                as: "article",
            },
        },
        {
            $project: {
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
                category: {
                    $getField: {
                        field: "category",
                        input: {
                            $arrayElemAt: ["$article", 0],
                        },
                    },
                },
            },
        },
        {
            $merge: READS,
        },
    ])
}

/**
 * Responsible for computing the BE-READS table from the READS table
 *
 * Group records by article
 * Sum all reads,agreements,comments,shares
 */
const computeBeReads = () => {
    db[READS].aggregate([
            {
                $group:
                    {
                        _id: "$aid",
                        timestamp: {$first: "$timestamp"},
                        aid: {$first: "$aid"},
                        category: {$first: "$category"},
                        readNum: {$sum: {$toInt: "$readTimeLength"}},
                        readUidList: {
                            $addToSet: {
                                $cond: {
                                    if: {
                                        $eq: ["$readOrNot", "1"],
                                    },
                                    then: "$uid",
                                    else: "$REMOVE",
                                },
                            },
                        },
                        commentNum: {$sum: {$toInt: "$commentOrNot"}},
                        commentUidList: {
                            $addToSet: {
                                $cond: {
                                    if: {
                                        $eq: ["$commentOrNot", "1"],
                                    },
                                    then: "$uid",
                                    else: "$REMOVE",
                                },
                            },
                        },
                        agreeNum: {$sum: {$toInt: "$agreeOrNot"}},
                        agreeUidList: {
                            $addToSet: {
                                $cond: {
                                    if: {
                                        $eq: ["$agreeOrNot", "1"],
                                    },
                                    then: "$uid",
                                    else: "$REMOVE",
                                },
                            },
                        },
                        shareNum: {$sum: {$toInt: "$shareOrNot"}},
                        shareUidList: {
                            $addToSet: {
                                $cond: {
                                    if: {
                                        $eq: ["$shareOrNot", "1"],
                                    },
                                    then: "$uid",
                                    else: "$REMOVE",
                                },
                            },
                        },
                    }
            },
            {
                $out: BE_READS,
            },
        ],
        {allowDiskUse: true})
}

/**
 * Responsible for computing the POPULAR-RANK table
 *
 * Iterate through each granularity -> "day", "week","month"
 *
 * Compute the total interacitons from the BE-READ table
 */
const computePopularRank = () => {
    const granularity = ["day", "week", "month"];

    granularity.forEach(temporalGranularity => {
        // Use the $dateTrunc operator to truncate the timestamp field of the be-read table according to the temporal granularity value.
        // This will create a new field that represents the start of the period for each document.
        db.beRead.aggregate([
            {
                $set: {
                    period: {
                        $dateTrunc: {
                            date: {$toDate: {$toLong: "$timestamp"}},
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
                    // readCount: {$sum: "$readNum"},
                    // commentCount: {$sum: "$commentNum"},
                    // agreeCount: {$sum: "$agreeNum"},
                    // shareCount: {$sum: "$shareNum"},
                    totalInteractions: {
                        $sum: {
                            $add: [
                                "$readNum",
                                "$commentNum",
                                "$agreeNum",
                                "$shareNum",
                            ]
                        }
                    },
                    // aid: {$first: "$aid"}, // the first article id for each period
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
                    _id: {$toLong: "$_id"},
                    timestamp: {$toLong: "$_id"},
                    period: "$_id",
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

// TODO: Add script for populating the data

computeMaterializedView(ARTICLES, "category", "science", ARTICLES_SCIENCE);
computeMaterializedView(BE_READS, "category", "science", BE_READS_SCIENCE);

alternateReads();
computeBeReads();
computePopularRank();