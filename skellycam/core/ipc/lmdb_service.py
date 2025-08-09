import json
import logging
from pathlib import Path
from typing import Any

import lmdb
import numpy as np
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)
# Define the LMDB database path
LMDB_CONFIG_PATH =str( Path(__file__).parent.parent.parent.parent / 'shared' / 'skellycam_lmdb_config.json')
if not Path(LMDB_CONFIG_PATH).exists():
    raise FileNotFoundError(f"LMDB configuration file not found at {LMDB_CONFIG_PATH}")


class LmdbSchema(BaseModel):
    keyFormat: str
    valueFormat: str

class LmdbConfig(BaseModel):
    dbPath: str
    mapSize: int
    maxDbs: int
    compression: bool
    schemas: dict[str, LmdbSchema]

    @property
    def db_full_path(self) -> str:
        return str(Path(self.dbPath.replace('~', str(Path.home()))))

    @classmethod
    def load_from_json(cls, path: str) -> 'LmdbConfig':
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)

class LmdbService(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    lmdb_config: LmdbConfig
    lmdb_environment: lmdb.Environment | None = None
    dbs: dict[str, lmdb._Database] = {}

    @classmethod
    def from_config(cls, lmdb_config_path: str = LMDB_CONFIG_PATH) -> 'LmdbService':
        lmdb_config = LmdbConfig.load_from_json(lmdb_config_path)
        # Set up database path
        Path(lmdb_config.db_full_path).mkdir(parents=True, exist_ok=True)
        return cls(lmdb_config=lmdb_config)

    def initialize(self) -> bool:
        """Initialize the LMDB environment and databases."""
        try:
            self.lmdb_environment = lmdb.open(
                self.lmdb_config.db_full_path,
                map_size=self.lmdb_config.mapSize,
                max_dbs=self.lmdb_config.maxDbs,
                create=True,
            )

            # Open named databases based on schema config
            for db_name in self.lmdb_config.schemas.keys():
                self.dbs[db_name] = self.lmdb_environment.open_db(b'db_name')

            logger.success(f"LMDB initialized at: {self.lmdb_config.db_full_path}, using lmdb version: {lmdb.version()}, \n\n self.lmdb_environment.info(): {self.lmdb_environment.info()}, \n\n  self.lmdb_environment.stat(): {self.lmdb_environment.stat()}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize LMDB: {e}")
            return False
    
    def get(self, db_name: str, key: str) -> Any:
        """Get a value from the database."""
        if not self.lmdb_environment or db_name not in self.dbs:
            raise ValueError(f"Database {db_name} not initialized")
        
        try:
            with self.lmdb_environment.begin(db=self.dbs[db_name]) as lmdb_transaction:
                value = lmdb_transaction.get(b'key')
                if value is None:
                    return None
                
                # Handle different value formats based on schema
                value_format = self.lmdb_config.schemas[db_name].valueFormat
                if value_format == 'json':
                    return json.loads(value)
                else:
                    raise NotImplementedError(f"Unsupported value format (for now): {value_format}")
        except Exception as e:
            logger.error(f"Error getting key {key} from {db_name}: {e}")
            return None
    
    def put(self, db_name: str, key: str, value: Any) -> bool:
        """Put a value into the database."""
        if not self.lmdb_environment or db_name not in self.dbs:
            raise ValueError(f"Database {db_name} not initialized")
        
        try:
            # Handle different value formats based on schema
            value_format = self.lmdb_config.schemas[db_name].valueFormat
            if value_format == 'json':
                encoded_value = json.dumps(value).encode()
            else:
                raise NotImplementedError(f"Unsupported value format (for now): {value_format}")
            
            with self.lmdb_environment.begin(write=True, db=self.dbs[db_name]) as lmdb_transaction:
                lmdb_transaction.put(b'key', encoded_value)
            return True
        except Exception as e:
            logger.error(f"Error putting key {key} to {db_name}: {e}")
            return False
    
    def remove(self, db_name: str, key: str) -> bool:
        """Remove a key from the database."""
        if not self.lmdb_environment or db_name not in self.dbs:
            raise ValueError(f"Database {db_name} not initialized")
        
        try:
            with self.lmdb_environment.begin(write=True, db=self.dbs[db_name]) as lmdb_transaction:
                lmdb_transaction.delete(b'key')
            return True
        except Exception as e:
            logger.error(f"Error removing key {key} from {db_name}: {e}")
            return False
    
    def close(self) -> None:
        """Close the LMDB environment."""
        if self.lmdb_environment:
            self.lmdb_environment.close()
            self.lmdb_environment = None
            self.dbs = {}
            logger.info("LMDB database closed")

    def list_keys(self, db_name: str, prefix: str = None) -> list[str]:
        """List all keys in a database, optionally filtered by prefix."""
        if not self.lmdb_environment or db_name not in self.dbs:
            raise ValueError(f"Database {db_name} not initialized")

        keys = []
        try:
            with self.lmdb_environment.begin(db=self.dbs[db_name]) as lmdb_transaction:
                cursor = lmdb_transaction.cursor()
                for key, _ in cursor:
                    decoded_key = key.decode('utf-8')
                    if prefix is None or decoded_key.startswith(prefix):
                        keys.append(decoded_key)
            return keys
        except Exception as e:
            logger.error(f"Error listing keys from {db_name}: {e}")
            return []

LMDB_SERVICE: LmdbService|None = None
def get_or_create_lmdb_service()-> LmdbService:
    global LMDB_SERVICE
    if LMDB_SERVICE is None:
        LMDB_SERVICE = LmdbService.from_config(LMDB_CONFIG_PATH)
        if not LMDB_SERVICE.initialize():
            LMDB_SERVICE = None
            raise RuntimeError("Failed to initialize LMDB service")
    return LMDB_SERVICE

if __name__ == "__main__":
    from skellycam.system.logging_configuration.configure_logging import configure_logging, LogLevels
    configure_logging(LogLevels.TRACE)
    # Example usage
    lmdb_service = get_or_create_lmdb_service()

    # Example of putting a value
    lmdb_service.put('metadata', 'test_key', {'example': 'value'})
    lmdb_service.put('metadata', 'test_key2', {'example': 'value'})

    # Example of getting a value
    value = lmdb_service.get('metadata', 'test_key')
    logger.debug(f"Retrieved value : {value} from 'metadata' for key 'test_key'")
    keys = lmdb_service.list_keys('metadata')
    logger.debug(f"Keys in 'metadata': {keys}")

    # Example of removing a key
    lmdb_service.remove('metadata', 'test_key')

    keys = lmdb_service.list_keys('metadata')
    logger.debug(f"Keys in 'metadata': {keys}")
    # Close the service when done
    lmdb_service.close()