import React, { useState, useEffect } from 'react';
import { getCircuitBreakerStatus, resetCircuitBreaker } from '../lib/api';

interface ApiStatusProps {
  className?: string;
}

export function ApiStatus({ className = '' }: ApiStatusProps) {
  const [status, setStatus] = useState(getCircuitBreakerStatus());
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setStatus(getCircuitBreakerStatus());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const handleReset = () => {
    resetCircuitBreaker();
    setStatus(getCircuitBreakerStatus());
  };

  const getStatusColor = () => {
    if (status.isOpen) return 'text-red-600 bg-red-50';
    if (status.failureCount > 0) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const getStatusText = () => {
    if (status.isOpen) return '🚨 Circuit Breaker OPEN';
    if (status.failureCount > 0) return `⚠️ ${status.failureCount} failures`;
    return '✅ API Healthy';
  };

  return (
    <div className={`fixed bottom-4 right-4 z-50 ${className}`}>
      {/* Toggle button */}
      <button
        onClick={() => setIsVisible(!isVisible)}
        className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${getStatusColor()}`}
        title="API Status"
      >
        {getStatusText()}
      </button>

      {/* Detailed status panel */}
      {isVisible && (
        <div className="absolute bottom-12 right-0 bg-white border border-gray-200 rounded-lg shadow-lg p-4 min-w-64">
          <div className="flex justify-between items-center mb-3">
            <h3 className="font-semibold text-gray-900">API Status</h3>
            <button
              onClick={() => setIsVisible(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Status:</span>
              <span className={status.isOpen ? 'text-red-600' : 'text-green-600'}>
                {status.isOpen ? 'OPEN' : 'CLOSED'}
              </span>
            </div>

            <div className="flex justify-between">
              <span className="text-gray-600">Failures:</span>
              <span className="text-gray-900">{status.failureCount}</span>
            </div>

            <div className="flex justify-between">
              <span className="text-gray-600">Last failure:</span>
              <span className="text-gray-900">
                {status.lastFailureTime > 0
                  ? `${Math.floor(status.timeSinceLastFailure / 1000)}s ago`
                  : 'Never'
                }
              </span>
            </div>
          </div>

          {status.isOpen && (
            <button
              onClick={handleReset}
              className="mt-3 w-full px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
            >
              Reset Circuit Breaker
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default ApiStatus;
