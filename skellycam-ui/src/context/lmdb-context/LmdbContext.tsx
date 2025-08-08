import React, { createContext, useContext, useEffect, useState } from 'react';
import { open } from 'lmdb';
// Define the shape of our context
interface LmdbContextType {
  isInitialized: boolean;
  latestCounter: number | null;
  error: string | null;
}


// Create the context with default values
const LmdbContext = createContext<LmdbContextType>({
  isInitialized: false,
  latestCounter: null,
  error: null,
});

interface LmdbProviderProps {
  children: React.ReactNode;
}

export const LmdbContextProvider: React.FC<LmdbProviderProps> = ({ children }) => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [latestCounter, setLatestCounter] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initialize the LMDB service when the component mounts
  useEffect(() => {
      let myDB = open({
          path: 'my-db',
          // any options go here, we can turn on compression like this:
          compression: true,
      });
      myDB.transaction(() => {
          myDB.put('greeting', { someText: 'Hello, World!' });
          myDB.get('greeting').someText // 'Hello, World!'
      });

    // Clean up when the component unmounts
    return () => {
        myDB.close();
    };
  }, []);

  // Create the context value
  const contextValue: LmdbContextType = {
    isInitialized,
    latestCounter,
    error,
  };

  return (
    <LmdbContext.Provider value={contextValue}>
      {children}
    </LmdbContext.Provider>
  );
};

// Custom hook to use the LMDB context
export const useLmdb = () => useContext(LmdbContext);
