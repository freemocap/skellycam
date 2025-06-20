/**
 * Application Configuration for Electron
 * 
 * This module centralizes all configuration settings for the application,
 * including environment-specific settings, API endpoints, and other constants.
 */

// In Electron, we can check if we're in the main or renderer process
// For simplicity, we'll use a more direct approach that works in the renderer
const isDevelopment = window.electron?.isDevelopment || false;
const isProduction = !isDevelopment;
const isTest = window.electron?.isTest || false;
// Base configuration
const config = {
  // Server configuration
  server: {
    host: 'localhost', // Default for local development
    port: 8006, // Default port
    protocol: 'http',
    wsProtocol: 'ws',
    basePath: '/skellycam',
  },
  
  // Feature flags
  features: {
    enableDebugLogging: isDevelopment || isTest,
    enableMockApi: false,
  },
  
  // Application settings
  settings: {
    defaultRecordingDirectory: '',
    maxReconnectAttempts: 30,
    reconnectBackoffFactor: 2,
    maxReconnectDelay: 30000, // 30 seconds
  }
};

// If we have access to electron's store, override defaults with stored values
if (window.electron?.store) {
  const storedConfig = window.electron.store.get('appConfig');
  if (storedConfig) {
    // Deep merge the stored config with our defaults
    Object.keys(storedConfig).forEach(key => {
      if (typeof storedConfig[key] === 'object' && storedConfig[key] !== null) {
        config[key] = { ...config[key], ...storedConfig[key] };
      } else {
        config[key] = storedConfig[key];
      }
    });
  }
}

export default config;