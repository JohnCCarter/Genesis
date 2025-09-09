import { useState, useCallback } from 'react';

export interface ApiError {
  message: string;
  type: 'timeout' | 'network' | 'server' | 'circuit_breaker' | 'unknown';
  timestamp: number;
  retryable: boolean;
}

export function useApiError() {
  const [error, setError] = useState<ApiError | null>(null);

  const handleError = useCallback((error: unknown): ApiError => {
    let apiError: ApiError;

    if (error instanceof Error) {
      const message = error.message.toLowerCase();
      
      if (message.includes('timeout')) {
        apiError = {
          message: 'Request timed out - server may be slow',
          type: 'timeout',
          timestamp: Date.now(),
          retryable: true,
        };
      } else if (message.includes('circuit breaker')) {
        apiError = {
          message: 'Backend is temporarily unavailable',
          type: 'circuit_breaker',
          timestamp: Date.now(),
          retryable: true,
        };
      } else if (message.includes('network') || message.includes('fetch')) {
        apiError = {
          message: 'Network connection failed',
          type: 'network',
          timestamp: Date.now(),
          retryable: true,
        };
      } else if (message.includes('http 5')) {
        apiError = {
          message: 'Server error - please try again later',
          type: 'server',
          timestamp: Date.now(),
          retryable: true,
        };
      } else {
        apiError = {
          message: error.message,
          type: 'unknown',
          timestamp: Date.now(),
          retryable: false,
        };
      }
    } else {
      apiError = {
        message: 'An unexpected error occurred',
        type: 'unknown',
        timestamp: Date.now(),
        retryable: false,
      };
    }

    setError(apiError);
    return apiError;
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const getErrorMessage = useCallback((error: ApiError): string => {
    const timeAgo = Math.floor((Date.now() - error.timestamp) / 1000);
    const timeStr = timeAgo < 60 ? `${timeAgo}s ago` : `${Math.floor(timeAgo / 60)}m ago`;
    
    return `${error.message} (${timeStr})`;
  }, []);

  const getErrorIcon = useCallback((error: ApiError): string => {
    switch (error.type) {
      case 'timeout': return '⏱️';
      case 'network': return '🌐';
      case 'server': return '🖥️';
      case 'circuit_breaker': return '🚨';
      default: return '❌';
    }
  }, []);

  return {
    error,
    handleError,
    clearError,
    getErrorMessage,
    getErrorIcon,
  };
}

export default useApiError;
