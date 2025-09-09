import React, { useState, useEffect } from 'react';
import { getCircuitBreakerStatus, resetCircuitBreaker, getApiBase } from '../lib/api';

interface BackendStatusProps {
  className?: string;
}

export function BackendStatus({ className = '' }: BackendStatusProps) {
  const [status, setStatus] = useState(getCircuitBreakerStatus());
  const [isChecking, setIsChecking] = useState(false);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setStatus(getCircuitBreakerStatus());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const handleCheckBackend = async () => {
    setIsChecking(true);
    try {
      // Try to reset circuit breaker and test connection
      resetCircuitBreaker();
      
      // Wait a moment for reset to take effect
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Test with a simple health check
      const response = await fetch(`${getApiBase()}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000), // 5 second timeout
      });
      
      if (response.ok) {
        setStatus(getCircuitBreakerStatus());
        setLastCheck(new Date());
      }
    } catch (error) {
      console.warn('Backend still not responding:', error);
    } finally {
      setIsChecking(false);
    }
  };

  const getStatusColor = () => {
    if (status.isOpen) return 'text-red-600 bg-red-50 border-red-200';
    if (status.failureCount > 0) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-green-600 bg-green-50 border-green-200';
  };

  const getStatusText = () => {
    if (status.isOpen) return '🚨 Backend Offline';
    if (status.failureCount > 0) return `⚠️ Backend Issues (${status.failureCount} failures)`;
    return '✅ Backend Online';
  };

  const getRecoveryTime = () => {
    if (!status.isOpen) return null;
    
    const timeSinceFailure = Date.now() - status.lastFailureTime;
    const recoveryTime = 30000 - timeSinceFailure; // 30 second recovery timeout
    
    if (recoveryTime <= 0) {
      return 'Ready for retry';
    }
    
    return `Retry in ${Math.ceil(recoveryTime / 1000)}s`;
  };

  return (
    <div className={`fixed top-4 right-4 z-50 ${className}`}>
      <div className={`px-4 py-3 rounded-lg border shadow-sm ${getStatusColor()}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium">{getStatusText()}</span>
            {isChecking && <span className="text-xs">🔄 Checking...</span>}
          </div>
          
          {status.isOpen && (
            <button
              onClick={handleCheckBackend}
              disabled={isChecking}
              className="ml-3 px-2 py-1 text-xs bg-white border border-current rounded hover:bg-gray-50 disabled:opacity-50"
            >
              {isChecking ? 'Checking...' : 'Check Backend'}
            </button>
          )}
        </div>
        
        {status.isOpen && (
          <div className="mt-2 text-xs">
            <div>Failures: {status.failureCount}</div>
            <div>{getRecoveryTime()}</div>
            {lastCheck && (
              <div>Last check: {lastCheck.toLocaleTimeString()}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default BackendStatus;
