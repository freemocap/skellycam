// skellycam-ui/src/contexts/grpc-context/grpcInitializer.ts
declare global {
  interface Window {
    nodeAPI: {
      require: (module: string) => any;
      process: {
        env: Record<string, string>;
        platform: string;
        versions: Record<string, string>;
      };
    };
  }
}

// Initialize gRPC modules using the Node.js require function exposed in preload
let niceGrpc: any;

// Try to initialize gRPC modules
try {
  // Use the exposed require function to load gRPC modules
  if (window.nodeAPI && window.nodeAPI.require) {
    // Load nice-grpc using Node.js require
    niceGrpc = window.nodeAPI.require('nice-grpc');
    console.log('Successfully loaded nice-grpc using Node.js require');
  } else {
    console.error('Node.js require function is not available');
    // Fallback to ESM imports (which might not work in this context)
    import('nice-grpc').then(module => {
      niceGrpc = module;
      console.log('Loaded nice-grpc using ESM import');
    }).catch(error => {
      console.error('Failed to load nice-grpc using ESM import:', error);
    });
  }
} catch (error) {
  console.error('Error initializing gRPC modules:', error);
}

// Export the initialized modules
export const { createChannel, createClient } = niceGrpc || {};