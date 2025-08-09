// src/context/lmdb-context/LmdbContext.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';
import path from 'path';

// Define the shape of our context
interface LmdbContextType {
  isInitialized: boolean;
  error: string | null;
  testData: Record<string, any> | null;
  dbPath: string | null;
  get: <T>(key: string) => Promise<T | null>;
  put: <T>(key: string, value: T) => Promise<boolean>;
  remove: (key: string) => Promise<boolean>;
}

// Create the context with default values
const LmdbContext = createContext<LmdbContextType>({
  isInitialized: false,
  error: null,
  testData: null,
  dbPath: null,
  get: async () => null,
  put: async () => false,
  remove: async () => false,
});

interface LmdbProviderProps {
  children: React.ReactNode;
}

export const LmdbContextProvider: React.FC<LmdbProviderProps> = ({ children }) => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testData, setTestData] = useState<Record<string, any> | null>(null);
  const [dbPath, setDbPath] = useState<string | null>(null);

  // Define the database operations
  const get = async <T,>(key: string): Promise<T | null> => {
    try {
      console.log(`LMDB: Getting value for key "${key}"`);
      const result = await window.lmdbAPI.get(key);
      console.log(`LMDB: Got value for key "${key}":`, result);
      return result as T | null;
    } catch (err) {
      const errorMsg = `Error getting key ${key}: ${err}`;
      console.error(`LMDB: ${errorMsg}`);
      setError(errorMsg);
      return null;
    }
  };

  const put = async <T,>(key: string, value: T): Promise<boolean> => {
    try {
      console.log(`LMDB: Putting value for key "${key}":`, value);
      const result = await window.lmdbAPI.put(key, value);
      console.log(`LMDB: Successfully put value for key "${key}"`);
      return result;
    } catch (err) {
      const errorMsg = `Error putting key ${key}: ${err}`;
      console.error(`LMDB: ${errorMsg}`);
      setError(errorMsg);
      return false;
    }
  };

  const remove = async (key: string): Promise<boolean> => {
    try {
      console.log(`LMDB: Removing key "${key}"`);
      const result = await window.lmdbAPI.remove(key);
      console.log(`LMDB: Successfully removed key "${key}"`);
      return result;
    } catch (err) {
      const errorMsg = `Error removing key ${key}: ${err}`;
      console.error(`LMDB: ${errorMsg}`);
      setError(errorMsg);
      return false;
    }
  };

  // Get database path
  useEffect(() => {
    const getDbPath = async () => {
      try {
        // Assuming you expose a method to get the path via IPC
        const path = await window.lmdbAPI.getDbPath();
        setDbPath(path);
        console.log(`LMDB: Database path: ${path}`);
      } catch (err) {
        console.error(`LMDB: Error getting database path: ${err}`);
      }
    };

    getDbPath();
  }, []);

  // Initialize and run test operations when component mounts
  useEffect(() => {
    const initializeAndTest = async () => {
      console.log('LMDB: Initializing database and running test operations');

      try {
        // Test 1: Write a simple string
        console.log('LMDB: Test 1 - Writing a simple string');
        await put('test-string', 'Hello from LMDB!');

        // Test 2: Write a complex object
        console.log('LMDB: Test 2 - Writing a complex object');
        const testObject = {
          name: 'SkellyCam',
          version: '2.0.0',
          features: ['Camera Control', 'Video Recording', 'Data Storage'],
          settings: {
            resolution: '1080p',
            framerate: 30,
            compression: true
          },
          timestamp: new Date().toISOString(),
          dbLocation: dbPath || 'Unknown'
        };
        await put('test-object', testObject);

        // Test 3: Read back the values
        console.log('LMDB: Test 3 - Reading back values');
        const stringValue = await get<string>('test-string');
        const objectValue = await get<typeof testObject>('test-object');

        // Store test results
        const testResults = {
          string: stringValue,
          object: objectValue,
          dbPath: dbPath
        };
        setTestData(testResults);

        console.log('LMDB: All tests completed successfully!');
        console.log(`LMDB: Test data: \n ${JSON.stringify(testResults, null, 2)}`);

        // Set initialized state
        setIsInitialized(true);
      } catch (err) {
        const errorMsg = `Failed to initialize and test LMDB: ${err}`;
        console.error(`LMDB: ${errorMsg}`);
        setError(errorMsg);
      }
    };

    initializeAndTest();
  }, [dbPath]);

  // Create the context value
  const contextValue: LmdbContextType = {
    isInitialized,
    error,
    testData,
    dbPath,
    get,
    put,
    remove,
  };

  return (
    <LmdbContext.Provider value={contextValue}>
      {children}
    </LmdbContext.Provider>
  );
};

// Custom hook to use the LMDB context
export const useLmdb = () => useContext(LmdbContext);
