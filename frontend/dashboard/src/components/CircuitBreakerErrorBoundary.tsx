import React, { Component, ErrorInfo, ReactNode } from 'react';
import { getCircuitBreakerStatus, resetCircuitBreaker, checkBackendHealth } from '../lib/api';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  isCircuitBreakerOpen: boolean;
  isCheckingBackend: boolean;
}

export class CircuitBreakerErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      isCircuitBreakerOpen: false,
      isCheckingBackend: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    const isCircuitBreakerError = error.message.includes('Circuit breaker is OPEN');

    return {
      hasError: true,
      error,
      isCircuitBreakerOpen: isCircuitBreakerError,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('CircuitBreakerErrorBoundary caught an error:', error, errorInfo);

    // Check if it's a circuit breaker error
    if (error.message.includes('Circuit breaker is OPEN')) {
      this.setState({ isCircuitBreakerOpen: true });
    }
  }

  handleCheckBackend = async () => {
    this.setState({ isCheckingBackend: true });

    try {
      // Reset circuit breaker
      resetCircuitBreaker();

      // Wait for reset to take effect
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Check if backend is available
      const isBackendOnline = await checkBackendHealth();

      if (isBackendOnline) {
        // Backend is back online, reset error state
        this.setState({
          hasError: false,
          error: null,
          isCircuitBreakerOpen: false,
          isCheckingBackend: false,
        });
      } else {
        this.setState({ isCheckingBackend: false });
      }
    } catch (error) {
      console.error('Failed to check backend:', error);
      this.setState({ isCheckingBackend: false });
    }
  };

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      isCircuitBreakerOpen: false,
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.state.isCircuitBreakerOpen) {
        return (
          <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
            <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
              <div className="text-center">
                <div className="text-6xl mb-4">🚨</div>
                <h1 className="text-xl font-semibold text-gray-900 mb-2">
                  Backend Connection Lost
                </h1>
                <p className="text-gray-600 mb-6">
                  The backend server appears to be offline. This could be due to:
                </p>

                <ul className="text-left text-sm text-gray-600 mb-6 space-y-2">
                  <li>• Backend server is not running</li>
                  <li>• Network connectivity issues</li>
                  <li>• Server is overloaded</li>
                </ul>

                <div className="space-y-3">
                  <button
                    onClick={this.handleCheckBackend}
                    disabled={this.state.isCheckingBackend}
                    className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {this.state.isCheckingBackend ? 'Checking...' : 'Check Backend'}
                  </button>

                  <button
                    onClick={this.handleRetry}
                    className="w-full px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
                  >
                    Retry Anyway
                  </button>
                </div>

                <div className="mt-4 text-xs text-gray-500">
                  <p>Circuit breaker status: OPEN</p>
                  <p>Failures: {getCircuitBreakerStatus().failureCount}</p>
                </div>
              </div>
            </div>
          </div>
        );
      }

      // Other errors
      return this.props.fallback || (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
            <div className="text-center">
              <div className="text-6xl mb-4">❌</div>
              <h1 className="text-xl font-semibold text-gray-900 mb-2">
                Something went wrong
              </h1>
              <p className="text-gray-600 mb-6">
                {this.state.error?.message || 'An unexpected error occurred'}
              </p>

              <button
                onClick={this.handleRetry}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default CircuitBreakerErrorBoundary;
