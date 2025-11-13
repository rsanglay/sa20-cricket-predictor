import React from 'react'
import { motion } from 'framer-motion'
import { Trophy, Award, Crown } from 'lucide-react'
import { TopPerformers as TopPerformersType } from '../types'

interface TopPerformersProps {
  performers: TopPerformersType
}

const TopPerformersComponent = ({ performers }: TopPerformersProps) => {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
      <h3 className="text-lg font-bold text-slate-900 mb-4">Top Performers</h3>
      <div className="space-y-4">
        {/* Orange Cap */}
        {performers.orangeCap && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-lg border border-orange-200 bg-orange-50 p-4"
          >
            <div className="flex items-center gap-3">
              <div className="bg-orange-500 rounded-full p-2">
                <Trophy className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <div className="text-xs text-orange-700 font-semibold mb-1 uppercase tracking-wider">Orange Cap</div>
                <div className="text-slate-900 font-bold">{performers.orangeCap.player_name}</div>
                <div className="text-sm text-slate-600">{performers.orangeCap.team_name}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-orange-600">{Math.round(performers.orangeCap.runs)}</div>
                <div className="text-xs text-slate-500">runs</div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Purple Cap */}
        {performers.purpleCap && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="rounded-lg border border-purple-200 bg-purple-50 p-4"
          >
            <div className="flex items-center gap-3">
              <div className="bg-purple-500 rounded-full p-2">
                <Award className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <div className="text-xs text-purple-700 font-semibold mb-1 uppercase tracking-wider">Purple Cap</div>
                <div className="text-slate-900 font-bold">{performers.purpleCap.player_name}</div>
                <div className="text-sm text-slate-600">{performers.purpleCap.team_name}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-purple-600">{Math.round(performers.purpleCap.wickets)}</div>
                <div className="text-xs text-slate-500">wickets</div>
              </div>
            </div>
          </motion.div>
        )}

        {/* MVP */}
        {performers.mvp && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="rounded-lg border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-yellow-50 p-4"
          >
            <div className="flex items-center gap-3">
              <div className="bg-amber-500 rounded-full p-2">
                <Crown className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <div className="text-xs text-amber-700 font-semibold mb-1 uppercase tracking-wider">MVP</div>
                <div className="text-slate-900 font-bold">{performers.mvp.player_name}</div>
                <div className="text-sm text-slate-600">{performers.mvp.team_name}</div>
              </div>
              <div className="text-right">
                <div className="text-lg font-bold text-amber-600">{Math.round(performers.mvp.runs)}/{Math.round(performers.mvp.wickets)}</div>
                <div className="text-xs text-slate-500">runs/wickets</div>
              </div>
            </div>
          </motion.div>
        )}

        {!performers.orangeCap && !performers.purpleCap && !performers.mvp && (
          <div className="text-center text-slate-500 py-8">No performers yet</div>
        )}
      </div>
    </div>
  )
}

// Memoize to prevent unnecessary re-renders
export const TopPerformers = React.memo(TopPerformersComponent)

