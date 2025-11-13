import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Coins, Circle } from 'lucide-react'

interface TossAnimationProps {
  homeTeam: string
  awayTeam: string
  tossWinner: 'home' | 'away'
  batFirst: 'home' | 'away'
}

export const TossAnimation = React.memo(({ homeTeam, awayTeam, tossWinner, batFirst }: TossAnimationProps) => {
  const [phase, setPhase] = useState<'flipping' | 'result' | 'decision'>('flipping')
  const tossWinnerName = tossWinner === 'home' ? homeTeam : awayTeam
  const batFirstName = batFirst === 'home' ? homeTeam : awayTeam
  const decision = batFirst === tossWinner ? 'BAT FIRST' : 'BOWL FIRST'

  useEffect(() => {
    // Phase 1: Coin flipping (2 seconds)
    const flipTimer = setTimeout(() => {
      setPhase('result')
    }, 2000)

    // Phase 2: Show decision (after 1 more second)
    const decisionTimer = setTimeout(() => {
      setPhase('decision')
    }, 4000)

    return () => {
      clearTimeout(flipTimer)
      clearTimeout(decisionTimer)
    }
  }, [])

  return (
    <div className="relative flex flex-col items-center justify-center min-h-screen px-8">
      {/* Animated background with team colors */}
      <motion.div 
        className="absolute inset-0 opacity-20"
        style={{ 
          background: `linear-gradient(135deg, rgba(251, 146, 60, 0.3), rgba(59, 130, 246, 0.3))`
        }}
        animate={{ opacity: [0.1, 0.3, 0.1] }}
        transition={{ duration: 2, repeat: Infinity }}
      />

      {/* Team names */}
      <motion.div
        initial={{ opacity: 0, y: -50 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="grid grid-cols-2 gap-8 mb-12 relative z-10"
      >
        <div className="text-center">
          <div className="text-2xl font-bold text-white mb-2">{homeTeam}</div>
          <div className="text-sm text-slate-400">Home</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-white mb-2">{awayTeam}</div>
          <div className="text-sm text-slate-400">Away</div>
        </div>
      </motion.div>

      {/* 3D Coin flip animation */}
      <div className="relative z-10 mb-12">
        <motion.div
          className="relative w-48 h-48"
          animate={{ 
            rotateY: phase === 'flipping' ? [0, 1800] : 0,
            scale: phase === 'flipping' ? [1, 1.2, 1] : 1,
          }}
          transition={{ 
            duration: phase === 'flipping' ? 2 : 0.3,
            ease: phase === 'flipping' ? [0.43, 0.13, 0.23, 0.96] : "easeOut",
          }}
          style={{ 
            transformStyle: 'preserve-3d',
            perspective: '1000px',
            willChange: 'transform',
          }}
        >
          {/* Coin front face */}
          <motion.div
            className="absolute inset-0 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 shadow-2xl flex items-center justify-center border-4 border-white/20"
            style={{
              backfaceVisibility: 'hidden',
              transform: 'translateZ(0)',
            }}
          >
            <Coins className="w-24 h-24 text-white" />
          </motion.div>
          
          {/* Coin back face (rotated) */}
          <motion.div
            className="absolute inset-0 rounded-full bg-gradient-to-br from-yellow-500 to-yellow-700 shadow-2xl flex items-center justify-center border-4 border-white/20"
            style={{
              backfaceVisibility: 'hidden',
              transform: 'rotateY(180deg) translateZ(0)',
            }}
          >
            <div className="text-6xl font-bold text-white">T</div>
          </motion.div>
        </motion.div>
      </div>

      {/* Result reveal */}
      {phase === 'result' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center relative z-10"
        >
          <motion.h2
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200 }}
            className="text-4xl font-bold text-white mb-4"
          >
            {tossWinnerName} won the toss!
          </motion.h2>
        </motion.div>
      )}

      {/* Decision reveal */}
      {phase === 'decision' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center relative z-10"
        >
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-slate-300 mb-4"
          >
            {tossWinnerName} won the toss and chose to
          </motion.p>
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.4, type: "spring", stiffness: 200 }}
            className="flex items-center justify-center gap-4 mb-4"
          >
            {/* Bat or Ball Icon */}
            {batFirst === tossWinner ? (
              <motion.div
                initial={{ rotate: -90, scale: 0 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ delay: 0.5, type: "spring", stiffness: 200 }}
                className="relative"
              >
                {/* Bat icon SVG */}
                <svg 
                  className="w-16 h-16 text-orange-400" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor" 
                  strokeWidth="2"
                >
                  <path d="M12 2L12 22M8 6L16 6M8 10L16 10" strokeLinecap="round" />
                  <path d="M6 14L18 14" strokeLinecap="round" strokeWidth="3" />
                </svg>
              </motion.div>
            ) : (
              <motion.div
                initial={{ rotate: 180, scale: 0 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ delay: 0.5, type: "spring", stiffness: 200 }}
                className="relative"
              >
                <Circle className="w-16 h-16 text-orange-400 fill-orange-400" strokeWidth={2} />
              </motion.div>
            )}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="text-3xl font-bold text-orange-400"
            >
              {decision}
            </motion.div>
          </motion.div>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="text-lg text-slate-400"
          >
            {batFirstName} will bat first
          </motion.p>
        </motion.div>
      )}
    </div>
  )
})

TossAnimation.displayName = 'TossAnimation'
