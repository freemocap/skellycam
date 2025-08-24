/**
 * URL Service
 *
 * Provides centralized URL generation for all API endpoints and WebSocket connections.
 * This ensures consistency across the application and simplifies changes to URL structure.
 */

import config from '@/config/appConfig';

class UrlService {
  /**
   * Builds the base URL for HTTP requests
   */
   getBaseHttpUrl(): string {
    const { httpProtocol, host, port } = config.server;
    return `${httpProtocol}://${host}:${port}${config.server.basePath}`;
  }

  /**
   * Builds the base WebSocket URL
   */
   getBaseWsUrl(): string {
    const { wsProtocol, host, port } = config.server;
    return `${wsProtocol}://${host}:${port}${config.server.basePath}`;
  }

  /**
   * Generates a complete API URL from a path
   */
  getApiUrl(path: string): string {
    return `${this.getBaseHttpUrl()}${path}`;
  }

  /**
   * Generates a WebSocket connection URL
   */
  getWebSocketUrl(path: string = '/websocket/connect'): string {
    return `${this.getBaseWsUrl()}${path}`;
  }

  // Camera API endpoints
  getCameraUrls() {
    return {
      detectCameras: this.getApiUrl('/camera/detect'),
      createGroup: this.getApiUrl('/camera/group/create'),
      closeAll: this.getApiUrl('/camera/group/close/all'),
      updateConfig: this.getApiUrl('/camera/update'),
      startRecording: this.getApiUrl('/camera/group/all/record/start'),
      stopRecording: this.getApiUrl('/camera/group/all/record/stop'),
      pauseCameras: this.getApiUrl('/camera/group/all/pause'),
      unpauseCameras: this.getApiUrl('/camera/group/all/unpause'),
    };
  }
}

// Export as a singleton
export const urlService = new UrlService();
