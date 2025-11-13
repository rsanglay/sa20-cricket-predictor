import { motion } from 'framer-motion'
import { useEffect } from 'react'
import confetti from 'canvas-confetti'
import { Team } from '../types'
import { Trophy } from 'lucide-react'

interface ChampionRevealProps {
  champion: Team
  onComplete: () => void
}

export const ChampionReveal = ({ champion, onComplete }: ChampionRevealProps) => {
  useEffect(() => {
    // Massive confetti explosion
    const duration = 5000
    const animationEnd = Date.now() + duration
    const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 10000 }

    function randomInRange(min: number, max: number) {
      return Math.random() * (max - min) + min
    }

    const interval = setInterval(() => {
      const timeLeft = animationEnd - Date.now()

      if (timeLeft <= 0) {
        return clearInterval(interval)
      }

      const particleCount = 50 * (timeLeft / duration)
      
      // Left side
      confetti({
        ...defaults,
        particleCount,
        origin: { x: randomInRange(0, 0.3), y: Math.random() - 0.2 },
        colors: ['#FFD700', '#FF6B35', '#004E89'],
      })
      
      // Right side
      confetti({
        ...defaults,
        particleCount,
        origin: { x: randomInRange(0.7, 1), y: Math.random() - 0.2 },
        colors: ['#FFD700', '#FF6B35', '#004E89'],
      })
      
      // Center burst
      if (Math.random() > 0.7) {
        confetti({
          ...defaults,
          particleCount: 100,
          origin: { x: 0.5, y: 0.5 },
          colors: ['#FFD700', '#FF6B35'],
        })
      }
    }, 250)

    // Auto-advance after 5 seconds
    setTimeout(() => {
      onComplete()
    }, 5000)

    return () => clearInterval(interval)
  }, [champion, onComplete])

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] flex items-center justify-center">
      <div className="text-center">
        <motion.div
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 100, damping: 10 }}
          className="mb-8"
        >
          <Trophy className="w-32 h-32 text-[#FFD700] mx-auto drop-shadow-2xl" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="text-7xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#FFD700] to-[#FF6B35] mb-4"
        >
          {champion.name.toUpperCase()}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-4xl font-bold text-white mb-8"
        >
          ARE YOUR SA20 2026 CHAMPIONS!
        </motion.p>

        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1 }}
          className="text-2xl text-slate-300"
        >
          🏆 🎉 🏆
        </motion.div>
      </div>
    </div>
  )
}

