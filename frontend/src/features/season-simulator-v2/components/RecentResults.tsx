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
    .filter(m => m.completed && m.winner_id && m.result)
    .slice(-maxResults)
    .reverse()

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
      <h3 className="text-lg font-bold text-slate-900 mb-4">Recent Results</h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        <AnimatePresence>
          {completedMatches.map((match) => {
            if (!match.result) return null

            const homeTeamBattedFirst = match.result.first_innings.team_id === match.home_team_id
            const homeScore = homeTeamBattedFirst 
              ? match.result.first_innings.runs 
              : match.result.second_innings.runs
            const homeWickets = homeTeamBattedFirst
              ? match.result.first_innings.wickets
              : match.result.second_innings.wickets
            const awayScore = !homeTeamBattedFirst
              ? match.result.first_innings.runs
              : match.result.second_innings.runs
            const awayWickets = !homeTeamBattedFirst
              ? match.result.first_innings.wickets
              : match.result.second_innings.wickets

            return (
              <motion.div
                key={match.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.3 }}
                className="rounded-lg border-l-4 border-emerald-500 bg-slate-50 p-3 pl-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Trophy className="w-4 h-4 text-emerald-600" />
                      <span className="text-slate-900 font-semibold text-sm">{match.winner_name}</span>
                    </div>
                    <div className="text-xs text-slate-600 mb-2">
                      {match.home_team_name} vs {match.away_team_name}
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-700">
                        <span className="font-medium">{match.home_team_name}:</span>{' '}
                        <span className="font-semibold">{homeScore}/{homeWickets}</span>
                      </div>
                      <div className="text-xs text-slate-700">
                        <span className="font-medium">{match.away_team_name}:</span>{' '}
                        <span className="font-semibold">{awayScore}/{awayWickets}</span>
                      </div>
                    </div>
                    <div className="text-xs text-emerald-600 font-semibold mt-2">
                      {match.winner_name} won by {match.result.margin}
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 ml-4">{match.venue_name}</div>
                </div>
              </motion.div>
            )
          })}
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

