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
  private getBaseUrl(): string {
    const { protocol, host, port } = config.server;
    return `${protocol}://${host}:${port}${config.server.basePath}`;
  }

  /**
   * Builds the base WebSocket URL
   */
  private getBaseWsUrl(): string {
    const { wsProtocol, host, port } = config.server;
    return `${wsProtocol}://${host}:${port}${config.server.basePath}`;
  }

  /**
   * Generates a complete API URL from a path
   */
  getApiUrl(path: string): string {
    return `${this.getBaseUrl()}${path}`;
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
      createGroup: this.getApiUrl('/camera/group/create'),
      closeAll: this.getApiUrl('/camera/group/close/all'),
      updateConfig: this.getApiUrl('/camera/update'),
      startRecording: this.getApiUrl('/camera/group/all/record/start'),
      stopRecording: this.getApiUrl('/camera/group/all/record/stop'),
    };
  }
}

// Export as a singleton
export const urlService = new UrlService();