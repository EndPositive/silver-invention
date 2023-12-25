import { USERS,ARTICLES,ARTICLES_SCIENCE,READS,BE_READS,BE_READS_SCIENCE,POPULAR_RANK } from "./config"

const collections = db.listCollections().toArray();
const collectionExists = (collectionName) => collections.some(collection => collection.name === collectionName);

const COLLECTIONS = [USERS,ARTICLES,ARTICLES_SCIENCE,READS,BE_READS,BE_READS_SCIENCE,POPULAR_RANK]

COLLECTIONS.forEach(collection => {
    if(!collectionExists(collection)){
        db.createCollection(collection)
    }
});