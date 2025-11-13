import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect } from 'react'
import { Match, Standing } from '../types'
import { Trophy, TrendingUp, Target, Zap } from 'lucide-react'

interface SeasonRewindProps {
  matches: Match[]
  standings: Standing[]
  onComplete: () => void
}

interface KeyMoment {
  id: string
  title: string
  description: string
  icon: React.ReactNode
  color: string
}

export const SeasonRewind = ({ matches, standings, onComplete }: SeasonRewindProps) => {
  const [currentMoment, setCurrentMoment] = useState(0)

  // Generate key moments
  const keyMoments: KeyMoment[] = [
    {
      id: '1',
      title: 'Biggest Upset',
      description: 'Underdog team stuns favorites',
      icon: <Zap className="w-8 h-8" />,
      color: 'from-yellow-500 to-orange-500',
    },
    {
      id: '2',
      title: 'Highest Score',
      description: 'Record-breaking team total',
      icon: <TrendingUp className="w-8 h-8" />,
      color: 'from-blue-500 to-cyan-500',
    },
    {
      id: '3',
      title: 'Best Bowling',
      description: 'Dominant bowling performance',
      icon: <Target className="w-8 h-8" />,
      color: 'from-purple-500 to-pink-500',
    },
    {
      id: '4',
      title: 'Close Finish',
      description: 'Nail-biting last-ball thriller',
      icon: <Trophy className="w-8 h-8" />,
      color: 'from-green-500 to-emerald-500',
    },
    {
      id: '5',
      title: 'Playoff Qualification',
      description: 'Top 4 teams secure their spots',
      icon: <Trophy className="w-8 h-8" />,
      color: 'from-[#FFD700] to-yellow-400',
    },
    {
      id: '6',
      title: 'Championship Moment',
      description: 'The moment of glory',
      icon: <Trophy className="w-8 h-8" />,
      color: 'from-[#FF6B35] to-[#FFD700]',
    },
  ]

  useEffect(() => {
    if (currentMoment < keyMoments.length - 1) {
      const timer = setTimeout(() => {
        setCurrentMoment(currentMoment + 1)
      }, 1500)
      return () => clearTimeout(timer)
    } else {
      setTimeout(() => {
        onComplete()
      }, 1500)
    }
  }, [currentMoment, keyMoments.length, onComplete])

  const current = keyMoments[currentMoment]

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] p-8">
      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-5xl font-bold text-white mb-12 text-center"
        >
          Season Rewind
        </motion.h2>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {keyMoments.map((moment, index) => (
            <AnimatePresence key={moment.id}>
              {index === currentMoment && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.8, rotateY: -90 }}
                  animate={{ opacity: 1, scale: 1, rotateY: 0 }}
                  exit={{ opacity: 0, scale: 0.8, rotateY: 90 }}
                  transition={{ duration: 0.5 }}
                  className={`col-span-2 md:col-span-3 bg-gradient-to-br ${moment.color} rounded-2xl p-8 border-2 border-white/20`}
                >
                  <div className="flex items-center justify-center gap-4 mb-4">
                    <div className="text-white">{moment.icon}</div>
                    <h3 className="text-3xl font-bold text-white">{moment.title}</h3>
                  </div>
                  <p className="text-xl text-white/90 text-center">{moment.description}</p>
                </motion.div>
              )}
            </AnimatePresence>
          ))}
        </div>

        {/* Progress Dots */}
        <div className="flex justify-center gap-2 mt-8">
          {keyMoments.map((_, index) => (
            <motion.div
              key={index}
              className={`w-3 h-3 rounded-full ${
                index === currentMoment ? 'bg-[#FF6B35]' : 'bg-slate-600'
              }`}
              animate={{
                scale: index === currentMoment ? 1.2 : 1,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

