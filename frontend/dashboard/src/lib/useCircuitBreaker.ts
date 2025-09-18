import { useState, useEffect, useCallback } from 'react';
import { getCircuitBreakerStatus, resetCircuitBreaker, checkBackendHealth } from './api';

export interface CircuitBreakerState {
  isOpen: boolean;
  failureCount: number;
  lastFailureTime: number;
  timeSinceLastFailure: number;
  recoveryTimeRemaining: number;
}

export function useCircuitBreaker() {
  const [state, setState] = useState<CircuitBreakerState>(() => {
    const status = getCircuitBreakerStatus();
    return {
      isOpen: status.isOpen,
      failureCount: status.failureCount,
      lastFailureTime: status.lastFailureTime,
      timeSinceLastFailure: status.timeSinceLastFailure,
      recoveryTimeRemaining: Math.max(0, 30000 - status.timeSinceLastFailure),
    };
  });

  const updateState = useCallback(() => {
    const status = getCircuitBreakerStatus();
    setState({
      isOpen: status.isOpen,
      failureCount: status.failureCount,
      lastFailureTime: status.lastFailureTime,
      timeSinceLastFailure: status.timeSinceLastFailure,
      recoveryTimeRemaining: Math.max(0, 30000 - status.timeSinceLastFailure),
    });
  }, []);

  useEffect(() => {
    const interval = setInterval(updateState, 1000);
    return () => clearInterval(interval);
  }, [updateState]);

  const checkBackend = useCallback(async (): Promise<boolean> => {
    try {
      // Reset circuit breaker
      resetCircuitBreaker();

      // Wait for reset to take effect
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Check backend health
      const isOnline = await checkBackendHealth();
      updateState();
      return isOnline;
    } catch (error) {
      console.error('Backend check failed:', error);
      updateState();
      return false;
    }
  }, [updateState]);

  const getStatusMessage = useCallback(() => {
    if (!state.isOpen) {
      return 'Backend connection is healthy';
    }

    if (state.recoveryTimeRemaining > 0) {
      return `Backend offline - auto-retry in ${Math.ceil(state.recoveryTimeRemaining / 1000)}s`;
    }

    return 'Backend offline - ready for manual retry';
  }, [state]);

  const getStatusIcon = useCallback(() => {
    if (!state.isOpen) return '✅';
    if (state.recoveryTimeRemaining > 0) return '⏳';
    return '🚨';
  }, [state]);

  const getStatusColor = useCallback(() => {
    if (!state.isOpen) return 'text-green-600 bg-green-50 border-green-200';
    if (state.recoveryTimeRemaining > 0) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  }, [state]);

  const canRetry = useCallback(() => {
    return state.isOpen && state.recoveryTimeRemaining <= 0;
  }, [state]);

  return {
    state,
    updateState,
    checkBackend,
    getStatusMessage,
    getStatusIcon,
    getStatusColor,
    canRetry,
  };
}

export default useCircuitBreaker;
