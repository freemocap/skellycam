// src/context/lmdb-context/LmdbContext.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';

// Define the shape of our context
interface LmdbContextType {
    isInitialized: boolean;
    error: string | null;
    testData: Record<string, any> | null;
    dbPath: string | null;
    get: <T>(dbName: string, key: string) => Promise<T | null>;
    put: <T>(dbName: string, key: string, value: T) => Promise<boolean>;
    remove: (dbName: string, key: string) => Promise<boolean>;
    listKeys: (dbName: string, prefix?: string) => Promise<string[]>;
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
    listKeys: async () => [],
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
    const get = async <T,>(dbName: string, key: string): Promise<T | null> => {
        try {
            console.log(`LMDB: Getting value for key "${key}" from database "${dbName}"`);
            const result = await window.lmdbAPI.get(dbName, key);
            console.log(`LMDB: Got value for key "${key}" from database "${dbName}":`, result);
            return result as T | null;
        } catch (err) {
            const errorMsg = `Error getting key ${key} from database ${dbName}: ${err}`;
            console.error(`LMDB: ${errorMsg}`);
            setError(errorMsg);
            return null;
        }
    };

    const put = async <T,>(dbName: string, key: string, value: T): Promise<boolean> => {
        try {
            console.log(`LMDB: Putting value for key "${key}" in database "${dbName}":`, value);
            const result = await window.lmdbAPI.put(dbName, key, value);
            console.log(`LMDB: Successfully put value for key "${key}" in database "${dbName}"`);
            return result;
        } catch (err) {
            const errorMsg = `Error putting key ${key} in database ${dbName}: ${err}`;
            console.error(`LMDB: ${errorMsg}`);
            setError(errorMsg);
            return false;
        }
    };

    const remove = async (dbName: string, key: string): Promise<boolean> => {
        try {
            console.log(`LMDB: Removing key "${key}" from database "${dbName}"`);
            const result = await window.lmdbAPI.remove(dbName, key);
            console.log(`LMDB: Successfully removed key "${key}" from database "${dbName}"`);
            return result;
        } catch (err) {
            const errorMsg = `Error removing key ${key} from database ${dbName}: ${err}`;
            console.error(`LMDB: ${errorMsg}`);
            setError(errorMsg);
            return false;
        }
    };

    const listKeys = async (dbName: string, prefix?: string): Promise<string[]> => {
        try {
            console.log(`LMDB: Listing keys in database "${dbName}"${prefix ? ` with prefix "${prefix}"` : ''}`);
            const result = await window.lmdbAPI.listKeys(dbName, prefix);
            console.log(`LMDB: Found ${result.length} keys in database "${dbName}"`);
            return result;
        } catch (err) {
            const errorMsg = `Error listing keys in database ${dbName}: ${err}`;
            console.error(`LMDB: ${errorMsg}`);
            setError(errorMsg);
            return [];
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
                // Test 1: Write to metadata database
                console.log('LMDB: Test 1 - Writing to metadata database');
                const metadataKey = 'test-metadata';
                const metadataValue = {
                    message: 'Hello from LMDB!',
                    timestamp: new Date().toISOString()
                };
                await put('metadata', metadataKey, metadataValue);

                // Test 2: Write to settings database
                console.log('LMDB: Test 2 - Writing to settings database');
                const settingsKey = 'app-settings';
                const settingsValue = {
                    name: 'SkellyCam',
                    version: '2.0.0',
                    features: ['Camera Control', 'Video Recording', 'Data Storage'],
                    settings: {
                        resolution: '1080p',
                        framerate: 30,
                        compression: false
                    },
                    timestamp: new Date().toISOString(),
                    dbLocation: dbPath || 'Unknown'
                };
                await put('settings', settingsKey, settingsValue);

                // Test 3: Read back the values
                console.log('LMDB: Test 3 - Reading back values');
                const metadataResult = await get('metadata', metadataKey);
                const settingsResult = await get('settings', settingsKey);

                // Test 4: List keys in databases
                console.log('LMDB: Test 4 - Listing keys in databases');
                const metadataKeys = await listKeys('metadata');
                const settingsKeys = await listKeys('settings');

                // Store test results
                const testResults = {
                    metadata: metadataResult,
                    settings: settingsResult,
                    metadataKeys,
                    settingsKeys,
                    dbPath
                };
                setTestData(testResults);

                console.log('LMDB: All tests completed successfully!');
                console.log(`LMDB: Test data: \n ${JSON.stringify(testResults, null, 2)}`);
                const pyResult = await get('metadata', 'test_key_python');
                console.log(`LMDB: Python test key result: ${JSON.stringify(pyResult)}`);
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
        listKeys,
    };

    return (
        <LmdbContext.Provider value={contextValue}>
            {children}
        </LmdbContext.Provider>
    );
};

// Custom hook to use the LMDB context
export const useLmdb = () => useContext(LmdbContext);
