import lmdb
import time
import os
import numpy as np
import json
from typing import Any

# Define the LMDB database path
LMDB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lmdb_data")

# Define the data structure
# We'll store data as JSON for flexibility
MAX_ITEMS = 100  # Maximum number of items to keep in the database

DUMMY_IMAGE = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
DUMMY_IMAGE_BYTES = DUMMY_IMAGE.tobytes()

def write_data() -> None:
    """Write data to the LMDB database."""
    # Create directory if it doesn't exist
    os.makedirs(LMDB_PATH, exist_ok=True)
    
    # Open the LMDB lmdb_environmentironment
    lmdb_environment = lmdb.open(
        LMDB_PATH,
        map_size=1024 * 1024 * 1024,  # 10MB should be plenty for our data
        max_dbs=1,  # We'll use two databases: one for data, one for metadata
        subdir=True
    )
    
    # Open named databases
    data_db = lmdb_environment.open_db(b'data')
    
    try:
        counter = 0
        
        while True:
            # Start a write transaction
            with lmdb_environment.begin(write=True) as txn:
                # Increment counter
                counter = (counter + 1) % MAX_ITEMS
                
            
                
                # Store data with counter as key
                tik = time.perf_counter()                
                for num in range(10):
                    txn.put(str("{counter}:{num}").encode('utf-8'), DUMMY_IMAGE_BYTES, db=data_db)
                tok = time.perf_counter()
                txn.put(b'latest_written', str(counter).encode('utf-8'), db=data_db)
                
                # Print status
                print(f"Wrote {(len(DUMMY_IMAGE_BYTES)*10)/1024:.3f} kB of data at index {counter}, and it toolk {tok - tik:.6f} seconds")
            
                # # Read data back to time read performance
                # tik = time.perf_counter()
                # for num in range(10):
                #     _ = txn.get(str("{counter}:{num}").encode('utf-8'), db=data_db)
                # tok = time.perf_counter()
                # print(f"Read {(len(DUMMY_IMAGE_BYTES)*10)/1024:.3f} kB of data at index {counter}, and it took {tok - tik:.6f} seconds")

    
    except KeyboardInterrupt:
        print("Stopping data writer")
    finally:
        lmdb_environment.close()

if __name__ == "__main__":
    write_data()