import { motion } from 'framer-motion'
import { Trophy, Award, Crown, Users } from 'lucide-react'
import { Team } from '../types'

interface TrophyPresentationProps {
  champion: Team
  orangeCap?: {
    player_id: number
    player_name: string
    team_name?: string
    runs: number
  } | null
  purpleCap?: {
    player_id: number
    player_name: string
    team_name?: string
    wickets: number
  } | null
  mvp?: {
    player_id: number
    player_name: string
    team_name?: string
    runs: number
    wickets: number
    score: number
  } | null
  onComplete: () => void
}

export const TrophyPresentation = ({ champion, orangeCap, purpleCap, mvp, onComplete }: TrophyPresentationProps) => {
  // Auto-advance after 10 seconds
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
          Trophy Presentation
        </motion.h2>

        {/* 3D Trophy */}
        <div className="flex justify-center mb-12">
          <motion.div
            animate={{ rotateY: [0, 360] }}
            transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
            style={{ transformStyle: 'preserve-3d', perspective: '1000px' }}
          >
            <Trophy className="w-48 h-48 text-[#FFD700] drop-shadow-2xl" />
          </motion.div>
        </div>

        {/* Champion */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
          className="bg-gradient-to-r from-[#FFD700]/20 to-yellow-900/20 rounded-2xl p-8 border-2 border-[#FFD700] mb-8 text-center"
        >
          <div className="text-4xl font-bold text-[#FFD700] mb-2">{champion.name}</div>
          <div className="text-2xl text-white">SA20 2026 Champions</div>
        </motion.div>

        {/* Awards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Orange Cap */}
          {orangeCap && (
            <motion.div
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 }}
              className="bg-gradient-to-br from-orange-900/30 to-orange-800/20 rounded-xl p-6 border border-orange-700/50"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="bg-orange-600 rounded-full p-3">
                  <Award className="w-8 h-8 text-white" />
                </div>
                <div className="text-orange-300 font-bold text-lg">Orange Cap</div>
              </div>
              <div className="text-white font-bold text-xl mb-1">{orangeCap.player_name}</div>
              <div className="text-slate-400 text-sm mb-2">{orangeCap.team_name}</div>
              <div className="text-3xl font-bold text-orange-400">{Math.round(orangeCap.runs)} runs</div>
            </motion.div>
          )}

          {/* Purple Cap */}
          {purpleCap && (
            <motion.div
              initial={{ opacity: 0, y: 50 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="bg-gradient-to-br from-purple-900/30 to-purple-800/20 rounded-xl p-6 border border-purple-700/50"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="bg-purple-600 rounded-full p-3">
                  <Award className="w-8 h-8 text-white" />
                </div>
                <div className="text-purple-300 font-bold text-lg">Purple Cap</div>
              </div>
              <div className="text-white font-bold text-xl mb-1">{purpleCap.player_name}</div>
              <div className="text-slate-400 text-sm mb-2">{purpleCap.team_name}</div>
              <div className="text-3xl font-bold text-purple-400">{Math.round(purpleCap.wickets)} wickets</div>
            </motion.div>
          )}

          {/* MVP */}
          {mvp && (
            <motion.div
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.9 }}
              className="bg-gradient-to-br from-[#FFD700]/20 to-yellow-900/20 rounded-xl p-6 border border-[#FFD700]/50"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="bg-[#FFD700] rounded-full p-3">
                  <Crown className="w-8 h-8 text-slate-900" />
                </div>
                <div className="text-[#FFD700] font-bold text-lg">MVP</div>
              </div>
              <div className="text-white font-bold text-xl mb-1">{mvp.player_name}</div>
              <div className="text-slate-400 text-sm mb-2">{mvp.team_name}</div>
              <div className="text-2xl font-bold text-[#FFD700]">
                {Math.round(mvp.runs)}/{Math.round(mvp.wickets)}
              </div>
              <div className="text-xs text-slate-400 mt-1">MVP Score: {Math.round(mvp.score)}</div>
            </motion.div>
          )}
        </div>

        {/* Tournament Stats */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.1 }}
          className="mt-8 text-center text-slate-400"
        >
          <div className="flex items-center justify-center gap-2">
            <Users className="w-5 h-5" />
            <span>33 matches • 6 teams • 1 champion</span>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

