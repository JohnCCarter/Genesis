import { useState, useEffect, useCallback } from 'react';
import { getCircuitBreakerStatus, resetCircuitBreaker, getApiBase } from './api';

export interface BackendStatus {
  isOnline: boolean;
  isCircuitBreakerOpen: boolean;
  failureCount: number;
  lastFailureTime: number;
  timeSinceLastFailure: number;
  recoveryTimeRemaining: number;
}

export function useBackendStatus() {
  const [status, setStatus] = useState<BackendStatus>(() => {
    const cbStatus = getCircuitBreakerStatus();
    return {
      isOnline: !cbStatus.isOpen,
      isCircuitBreakerOpen: cbStatus.isOpen,
      failureCount: cbStatus.failureCount,
      lastFailureTime: cbStatus.lastFailureTime,
      timeSinceLastFailure: cbStatus.timeSinceLastFailure,
      recoveryTimeRemaining: Math.max(0, 30000 - cbStatus.timeSinceLastFailure),
    };
  });

  const updateStatus = useCallback(() => {
    const cbStatus = getCircuitBreakerStatus();
    setStatus({
      isOnline: !cbStatus.isOpen,
      isCircuitBreakerOpen: cbStatus.isOpen,
      failureCount: cbStatus.failureCount,
      lastFailureTime: cbStatus.lastFailureTime,
      timeSinceLastFailure: cbStatus.timeSinceLastFailure,
      recoveryTimeRemaining: Math.max(0, 30000 - cbStatus.timeSinceLastFailure),
    });
  }, []);

  useEffect(() => {
    // Update status every second
    const interval = setInterval(updateStatus, 1000);
    return () => clearInterval(interval);
  }, [updateStatus]);

  const checkBackend = useCallback(async (): Promise<boolean> => {
    try {
      // Reset circuit breaker
      resetCircuitBreaker();

      // Wait for reset to take effect
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Test backend with health check
      const response = await fetch(`${getApiBase()}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });

      const isOnline = response.ok;
      updateStatus();
      return isOnline;
    } catch (error) {
      console.warn('Backend check failed:', error);
      updateStatus();
      return false;
    }
  }, [updateStatus]);

  const getStatusMessage = useCallback(() => {
    if (status.isOnline) {
      return 'Backend is online';
    }

    if (status.isCircuitBreakerOpen) {
      if (status.recoveryTimeRemaining > 0) {
        return `Backend offline - retry in ${Math.ceil(status.recoveryTimeRemaining / 1000)}s`;
      }
      return 'Backend offline - ready for retry';
    }

    if (status.failureCount > 0) {
      return `Backend issues - ${status.failureCount} recent failures`;
    }

    return 'Backend status unknown';
  }, [status]);

  const getStatusIcon = useCallback(() => {
    if (status.isOnline) return '✅';
    if (status.isCircuitBreakerOpen) return '🚨';
    if (status.failureCount > 0) return '⚠️';
    return '❓';
  }, [status]);

  const getStatusColor = useCallback(() => {
    if (status.isOnline) return 'text-green-600 bg-green-50';
    if (status.isCircuitBreakerOpen) return 'text-red-600 bg-red-50';
    if (status.failureCount > 0) return 'text-yellow-600 bg-yellow-50';
    return 'text-gray-600 bg-gray-50';
  }, [status]);

  return {
    status,
    updateStatus,
    checkBackend,
    getStatusMessage,
    getStatusIcon,
    getStatusColor,
  };
}

export default useBackendStatus;
