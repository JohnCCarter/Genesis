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

export default useThrottledValue;
