import { useState, useCallback, useRef, useEffect } from 'react'

interface AnimationTask {
  id: string
  duration: number
  callback: () => void
  onComplete?: () => void
}

export const useAnimationQueue = (speedMultiplier: number = 1) => {
  const [isAnimating, setIsAnimating] = useState(false)
  const queueRef = useRef<AnimationTask[]>([])
  const currentTaskRef = useRef<AnimationTask | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const processQueue = useCallback(() => {
    if (isAnimating || queueRef.current.length === 0) return

    const task = queueRef.current.shift()
    if (!task) return

    setIsAnimating(true)
    currentTaskRef.current = task

    // Execute callback
    task.callback()

    // Schedule completion
    const adjustedDuration = task.duration / speedMultiplier
    timeoutRef.current = setTimeout(() => {
      task.onComplete?.()
      setIsAnimating(false)
      currentTaskRef.current = null
      processQueue()
    }, adjustedDuration)
  }, [isAnimating, speedMultiplier])

  const addToQueue = useCallback((task: AnimationTask) => {
    queueRef.current.push(task)
    processQueue()
  }, [processQueue])

  const clearQueue = useCallback(() => {
    queueRef.current = []
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setIsAnimating(false)
    currentTaskRef.current = null
  }, [])

  // Process queue when speed multiplier changes
  useEffect(() => {
    if (!isAnimating && queueRef.current.length > 0) {
      processQueue()
    }
  }, [speedMultiplier, isAnimating, processQueue])

  return {
    addToQueue,
    clearQueue,
    isAnimating,
  }
}

