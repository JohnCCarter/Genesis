import React, { useState, useEffect } from 'react';
import { getCircuitBreakerStatus, resetCircuitBreaker, checkBackendHealth } from '../lib/api';

interface CircuitBreakerBannerProps {
  className?: string;
}

export function CircuitBreakerBanner({ className = '' }: CircuitBreakerBannerProps) {
  const [status, setStatus] = useState(getCircuitBreakerStatus());
  const [isChecking, setIsChecking] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      const newStatus = getCircuitBreakerStatus();
      setStatus(newStatus);

      // Show banner when circuit breaker is open
      if (newStatus.isOpen && !isVisible) {
        setIsVisible(true);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isVisible]);

  const handleCheckBackend = async () => {
    setIsChecking(true);
    try {
      // Reset circuit breaker
      resetCircuitBreaker();

      // Wait for reset to take effect
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Check if backend is actually available
      const isBackendOnline = await checkBackendHealth();

      if (isBackendOnline) {
        setIsVisible(false);
        console.log('✅ Backend is back online!');
      } else {
        console.warn('⚠️ Backend is still offline');
      }
    } catch (error) {
      console.error('❌ Failed to check backend:', error);
    } finally {
      setIsChecking(false);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
  };

  const getRecoveryTime = () => {
    if (!status.isOpen) return null;

    const timeSinceFailure = Date.now() - status.lastFailureTime;
    const recoveryTime = 30000 - timeSinceFailure; // 30 second recovery timeout

    if (recoveryTime <= 0) {
      return 'Ready for retry';
    }

    return `Auto-retry in ${Math.ceil(recoveryTime / 1000)}s`;
  };

  if (!isVisible || !status.isOpen) {
    return null;
  }

  return (
    <div className={`fixed top-0 left-0 right-0 z-50 bg-red-600 text-white ${className}`}>
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex-shrink-0">
              <span className="text-xl">🚨</span>
            </div>
            <div>
              <h3 className="text-sm font-medium">
                Backend Connection Lost
              </h3>
              <p className="text-sm text-red-100">
                {status.failureCount} connection failures detected.
                {getRecoveryTime() && ` ${getRecoveryTime()}`}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleCheckBackend}
              disabled={isChecking}
              className="px-3 py-1 text-sm bg-white text-red-600 rounded-md hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isChecking ? 'Checking...' : 'Check Backend'}
            </button>

            <button
              onClick={handleDismiss}
              className="px-3 py-1 text-sm text-red-100 hover:text-white"
            >
              ✕
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CircuitBreakerBanner;
