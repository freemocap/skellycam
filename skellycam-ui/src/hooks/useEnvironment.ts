import { useMemo } from 'react';
import config from '@/config/appConfig';
import { urlService } from '@/services/urlService';

/**
 * Hook that provides environment and configuration information
 */
export function useEnvironment() {
  return useMemo(() => ({
    isProduction: process.env.NODE_ENV === 'production',
    isDevelopment: process.env.NODE_ENV === 'development',
    isTest: process.env.NODE_ENV === 'test',
    config,
    apiBaseUrl: urlService.getApiUrl(''),
    wsBaseUrl: urlService.getWebSocketUrl(''),
  }), []);
}