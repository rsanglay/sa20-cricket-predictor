import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { Match } from '../types'
import { Play } from 'lucide-react'

interface FixtureRevealProps {
  matches: Match[]
  onComplete: () => void
}

export const FixtureReveal = ({ matches, onComplete }: FixtureRevealProps) => {
  const leagueMatches = matches.filter(m => m.match_type === 'league')
  const [canProceed, setCanProceed] = useState(false)

  // Allow proceeding after 3 seconds (enough time to see fixtures)
  useEffect(() => {
    const timer = setTimeout(() => {
      setCanProceed(true)
    }, 3000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] p-8">
      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl font-bold text-white mb-8 text-center"
        >
          Season Fixtures
        </motion.h2>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-8">
          {leagueMatches.length > 0 ? (
            leagueMatches.map((match, index) => (
              <motion.div
                key={match.id}
                initial={{ opacity: 0, scale: 0.8, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{
                  delay: index * 0.05,
                  duration: 0.5,
                  type: 'spring',
                  stiffness: 100,
                }}
                className="bg-slate-800/50 backdrop-blur-sm rounded-lg p-4 border border-slate-700 hover:border-[#FF6B35] transition-colors"
              >
                <div className="text-center">
                  <div className="text-sm text-slate-400 mb-2">Match {index + 1}</div>
                  <div className="text-white font-semibold text-sm mb-1">{match.home_team_name}</div>
                  <div className="text-slate-500 text-xs mb-1">vs</div>
                  <div className="text-white font-semibold text-sm">{match.away_team_name}</div>
                  <div className="text-xs text-slate-400 mt-2">{match.venue_name}</div>
                </div>
              </motion.div>
            ))
          ) : (
            <div className="col-span-full text-center text-slate-400 py-8">
              Loading fixtures...
            </div>
          )}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2 }}
          className="text-center"
        >
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="text-xl text-slate-300 mb-6"
          >
            Simulating 1000 parallel universes...
          </motion.p>

          {canProceed && (
            <motion.button
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onComplete}
              className="px-8 py-3 bg-gradient-to-r from-[#FF6B35] to-[#FF8C42] rounded-full text-white font-bold text-lg shadow-2xl hover:shadow-[#FF6B35]/50 transition-all duration-300 flex items-center gap-2 mx-auto"
            >
              <Play className="w-5 h-5" fill="currentColor" />
              Start Simulation
            </motion.button>
          )}
        </motion.div>
      </div>
    </div>
  )
}

