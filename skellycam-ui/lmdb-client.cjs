const lmdb = require('node-lmdb');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Read the LMDB configuration
const configPath = path.resolve(__dirname, 'C:\\Users\\jonma\\github_repos\\freemocap_organization\\skellycam\\shared\\skellycam_lmdb_config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

// Resolve the database path (replace ~ with home directory)
const dbPath = config.dbPath.replace('~', os.homedir());

function encodeKey(key) {
  // Encode the key as UTF-8 buffer
  return Buffer.from(String(key), 'utf8');
}

function decodeKey(key) {
  // Decode the key from UTF-8 buffer
  return key.toString('utf8');
}

// Initialize LMDB environment
const env = new lmdb.Env();
env.open({
  path: dbPath,
  mapSize: config.mapSize,
  maxDbs: config.maxDbs

});

// Open the databases based on schema config
const dbs = {};
Object.keys(config.schemas).forEach(dbName => {
  dbs[dbName] = env.openDbi({
    name: dbName,
    create: true
  });
});

function getValue(dbName, key) {
  if (!dbs[dbName]) {
    throw new Error(`Database ${dbName} not initialized`);
  }

  const txn = env.beginTxn({ readOnly: true });
  try {
    const encodedKey = encodeKey(key);
    const value = txn.getBinary(dbs[dbName], encodedKey);
    txn.commit();
    
    if (value) {
      // Convert Buffer to string
      const valueStr = value.toString('utf8');
      // Parse the JSON string if the format is JSON
      if (config.schemas[dbName].valueFormat === 'json') {
        return JSON.parse(valueStr);
      }
      return valueStr;
    }
    return null;
  } catch (error) {
    txn.abort();
    console.error(`Error getting key ${key} from ${dbName}:`, error);
    return null;
  }
}

function putValue(dbName, key, value) {
  if (!dbs[dbName]) {
    throw new Error(`Database ${dbName} not initialized`);
  }

  const txn = env.beginTxn();
  try {
    const encodedKey = encodeKey(key);
    // Handle different value formats based on schema
    const valueFormat = config.schemas[dbName].valueFormat;
    if (valueFormat === 'json') {
      const valueBuffer = Buffer.from(JSON.stringify(value), 'utf8');
      txn.putBinary(dbs[dbName], encodedKey, valueBuffer);
    } else {
      throw new Error(`Unsupported value format: ${valueFormat}`);
    }
    
    txn.commit();
    return true;
  } catch (error) {
    txn.abort();
    console.error(`Error putting key ${key} to ${dbName}:`, error);
    return false;
  }
}

// Helper function to remove a key
function removeValue(dbName, key) {
  if (!dbs[dbName]) {
    throw new Error(`Database ${dbName} not initialized`);
  }

  const txn = env.beginTxn();
  try {
    const encodedKey = encodeKey(key);
    txn.del(dbs[dbName], encodedKey);
    txn.commit();
    return true;
  } catch (error) {
    txn.abort();
    console.error(`Error removing key ${key} from ${dbName}:`, error);
    return false;
  }
}


// Close function to clean up
function close() {
  Object.values(dbs).forEach(db => db.close());
  env.close();
  console.log("LMDB database closed");
}

// Example usage
function runExample() {
  console.log("Running LMDB example...");
  
  // Example of putting a value
  putValue('metadata', 'test_key_node', { example: 'value from Node.js' });
  console.log("Added test_key_node to metadata");
  putValue('metadata', 'test_key_node2', { example2: '2value from Node.js' });
  console.log("Added test_key_node2 to metadata");

  // Example of getting a value
  const value = getValue('metadata', 'test_key_node');
  console.log("Retrieved value:", value);
  
  const pyvalue = getValue('metadata', 'test_key_python');
  console.log("Retrieved python- value:", pyvalue);
  
  
  // Close the database
  close();
}

// Run the example if this script is executed directly
if (require.main === module) {
  runExample();
} else {
  // Export functions for use as a module
  module.exports = {
    getValue,
    putValue,
    removeValue,
    listKeys,
    close
  };
}