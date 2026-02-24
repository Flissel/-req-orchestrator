/**
 * Performance utilities for debouncing and throttling
 */

/**
 * Creates a debounced function that delays invoking func until after
 * wait milliseconds have elapsed since the last time it was invoked.
 *
 * @param {Function} func - The function to debounce
 * @param {number} wait - The number of milliseconds to delay
 * @param {boolean} immediate - If true, trigger on leading edge instead of trailing
 * @returns {Function} - The debounced function with a cancel method
 */
export function debounce(func, wait, immediate = false) {
  let timeout = null
  let result

  const debounced = function (...args) {
    const context = this
    const later = () => {
      timeout = null
      if (!immediate) {
        result = func.apply(context, args)
      }
    }

    const callNow = immediate && !timeout

    clearTimeout(timeout)
    timeout = setTimeout(later, wait)

    if (callNow) {
      result = func.apply(context, args)
    }

    return result
  }

  debounced.cancel = () => {
    clearTimeout(timeout)
    timeout = null
  }

  return debounced
}

/**
 * Creates a throttled function that only invokes func at most once
 * per every wait milliseconds.
 *
 * @param {Function} func - The function to throttle
 * @param {number} wait - The number of milliseconds to throttle
 * @returns {Function} - The throttled function
 */
export function throttle(func, wait) {
  let lastCall = 0
  let timeout = null

  return function (...args) {
    const now = Date.now()
    const remaining = wait - (now - lastCall)

    if (remaining <= 0 || remaining > wait) {
      if (timeout) {
        clearTimeout(timeout)
        timeout = null
      }
      lastCall = now
      return func.apply(this, args)
    } else if (!timeout) {
      timeout = setTimeout(() => {
        lastCall = Date.now()
        timeout = null
        func.apply(this, args)
      }, remaining)
    }
  }
}

/**
 * React hook for debounced values
 * Usage: const debouncedValue = useDebounce(value, 300)
 */
export function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = React.useState(value)

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

/**
 * React hook for debounced callback
 * Usage: const debouncedCallback = useDebouncedCallback((value) => search(value), 300)
 */
export function useDebouncedCallback(callback, delay, deps = []) {
  const callbackRef = React.useRef(callback)

  React.useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  return React.useMemo(
    () => debounce((...args) => callbackRef.current(...args), delay),
    [delay, ...deps]
  )
}

// Import React for hooks (conditional to support non-React usage)
import * as React from 'react'
