"use client";

import { useState, useEffect } from "react";

/**
 * Debounce a value — delays updating until `delay` ms of inactivity.
 * Prevents excessive API calls from slider/input changes.
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
