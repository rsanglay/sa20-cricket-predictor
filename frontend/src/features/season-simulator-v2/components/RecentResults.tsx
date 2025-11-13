import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Match } from '../types'
import { Trophy } from 'lucide-react'

interface RecentResultsProps {
  matches: Match[]
  maxResults?: number
}

const RecentResultsComponent = ({ matches, maxResults = 5 }: RecentResultsProps) => {
  const completedMatches = matches
    .filter(m => m.completed && m.winner_id)
    .slice(-maxResults)
    .reverse()

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
      <h3 className="text-lg font-bold text-slate-900 mb-4">Recent Results</h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        <AnimatePresence>
          {completedMatches.map((match) => (
            <motion.div
              key={match.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
              className="rounded-lg border border-slate-200 bg-slate-50 p-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Trophy className="w-4 h-4 text-emerald-600" />
                    <span className="text-slate-900 font-semibold text-sm">{match.winner_name}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    {match.home_team_name} vs {match.away_team_name}
                  </div>
                  {match.home_score !== undefined && match.away_score !== undefined && match.winner_id && (
                    <div className="text-xs text-slate-500 mt-1">
                      {match.home_team_name}: {match.home_score} - {match.away_team_name}: {match.away_score}
                      {(() => {
                        const margin = Math.abs(match.home_score - match.away_score)
                        const winnerIsHome = match.winner_id === match.home_team_id
                        return (
                          <span className="text-emerald-600 font-semibold ml-2">
                            {winnerIsHome ? match.home_team_name : match.away_team_name} won by {margin} {margin === 1 ? 'run' : 'runs'}
                          </span>
                        )
                      })()}
                    </div>
                  )}
                </div>
                <div className="text-xs text-slate-500">{match.venue_name}</div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {completedMatches.length === 0 && (
          <div className="text-center text-slate-500 py-8">No matches completed yet</div>
        )}
      </div>
    </div>
  )
}

// Memoize to prevent unnecessary re-renders
export const RecentResults = React.memo(RecentResultsComponent)

