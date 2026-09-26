// Runs only on the first initialization of an empty persistent volume.
const application = db.getSiblingDB(process.env.MONGO_DATABASE);
application.createUser({
  user: process.env.MONGO_APP_USERNAME,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{role: 'readWrite', db: process.env.MONGO_DATABASE}]
});
application.createCollection('accidents', {
  validator: {$jsonSchema: {
    bsonType: 'object', required: ['location'],
    properties: {location: {
      bsonType: 'object', required: ['type', 'coordinates'],
      properties: {
        type: {enum: ['Point']},
        coordinates: {bsonType: 'array', minItems: 2, maxItems: 2,
          items: {bsonType: ['double', 'int', 'long', 'decimal']}}
      }
    }}
  }}, validationLevel: 'strict', validationAction: 'error'
});
application.accidents.createIndex({location: '2dsphere'}, {name: 'location_2dsphere'});
