import { useEffect, useRef, useState } from 'react';

type Timer = ReturnType<typeof setTimeout>;

export function useThrottledValue<T>(value: T, intervalMs = 300): T {
  const [throttled, setThrottled] = useState<T>(value);
  const lastTsRef = useRef<number>(Date.now());
  const timerRef = useRef<Timer | null>(null);

  useEffect(() => {
    const now = Date.now();
    const elapsed = now - lastTsRef.current;

    if (elapsed >= intervalMs) {
      lastTsRef.current = now;
      setThrottled(value);
      return;
    }

    const remaining = Math.max(0, intervalMs - elapsed);

    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    timerRef.current = setTimeout(() => {
      lastTsRef.current = Date.now();
      setThrottled(value);
      timerRef.current = null;
    }, remaining);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [value, intervalMs]);

  return throttled;
}

// Hook för att throttla API-anrop
export function useThrottledApiCall<T extends (...args: any[]) => Promise<any>>(
  apiCall: T,
  intervalMs = 1000
): T {
  const lastCallRef = useRef<number>(0);
  const pendingCallRef = useRef<Timer | null>(null);

  const throttledCall = useRef(async (...args: Parameters<T>): Promise<ReturnType<T>> => {
    const now = Date.now();
    const elapsed = now - lastCallRef.current;

    if (elapsed >= intervalMs) {
      lastCallRef.current = now;
      return apiCall(...args);
    }

    // Cancel any pending call
    if (pendingCallRef.current) {
      clearTimeout(pendingCallRef.current);
    }

    // Schedule the call for later
    return new Promise((resolve, reject) => {
      const remaining = intervalMs - elapsed;
      pendingCallRef.current = setTimeout(async () => {
        try {
          lastCallRef.current = Date.now();
          const result = await apiCall(...args);
          resolve(result);
        } catch (error) {
          reject(error);
        }
      }, remaining);
    });
  }).current;

  return throttledCall as T;
}

export default useThrottledValue;
