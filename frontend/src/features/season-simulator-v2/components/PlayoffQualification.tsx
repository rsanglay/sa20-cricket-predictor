import { motion } from 'framer-motion'
import { Standing } from '../types'
import { Trophy, X } from 'lucide-react'

interface PlayoffQualificationProps {
  standings: Standing[]
  onComplete: () => void
}

export const PlayoffQualification = ({ standings, onComplete }: PlayoffQualificationProps) => {
  const sortedStandings = [...standings].sort((a, b) => a.position - b.position)
  const top4 = sortedStandings.slice(0, 4)
  const bottom2 = sortedStandings.slice(4)

  // Auto-complete after animation
  setTimeout(() => {
    onComplete()
  }, 10000)

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] p-8">
      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-5xl font-bold text-white mb-12 text-center"
        >
          Playoff Qualification
        </motion.h2>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
          {sortedStandings.map((team, index) => {
            const isTop4 = index < 4
            const probability = team.playoff_probability

            return (
              <motion.div
                key={team.team_id}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: index * 0.2, duration: 0.5 }}
                className={`relative rounded-2xl p-6 border-2 ${
                  isTop4
                    ? 'bg-gradient-to-br from-[#FFD700]/20 to-yellow-900/20 border-[#FFD700]'
                    : 'bg-slate-800/50 border-slate-700 grayscale'
                }`}
              >
                {/* Team Info */}
                <div className="text-center mb-4">
                  <div className={`text-2xl font-bold mb-2 ${isTop4 ? 'text-[#FFD700]' : 'text-slate-500'}`}>
                    {team.team_name}
                  </div>
                  <div className="text-sm text-slate-400">Position: {team.position}</div>
                </div>

                {/* Probability Meter */}
                <div className="mb-4">
                  <div className="flex justify-between text-xs mb-2">
                    <span className={isTop4 ? 'text-[#FFD700]' : 'text-slate-400'}>Playoff Probability</span>
                    <span className={isTop4 ? 'text-[#FFD700]' : 'text-slate-400'}>{probability.toFixed(1)}%</span>
                  </div>
                  <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full ${isTop4 ? 'bg-gradient-to-r from-[#FFD700] to-yellow-600' : 'bg-slate-600'}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${probability}%` }}
                      transition={{ delay: index * 0.2 + 0.5, duration: 2, type: 'spring' }}
                    />
                  </div>
                </div>

                {/* Status Badge */}
                <div className="flex justify-center">
                  {isTop4 ? (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: index * 0.2 + 1.5, type: 'spring' }}
                      className="flex items-center gap-2 bg-[#FFD700] text-slate-900 px-4 py-2 rounded-full font-bold"
                    >
                      <Trophy className="w-5 h-5" />
                      QUALIFIED
                    </motion.div>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: index * 0.2 + 1.5 }}
                      className="flex items-center gap-2 text-slate-500 px-4 py-2 rounded-full font-semibold"
                    >
                      <X className="w-5 h-5" />
                      ELIMINATED
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

