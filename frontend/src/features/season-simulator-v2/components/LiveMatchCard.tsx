import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect } from 'react'
import confetti from 'canvas-confetti'
import { Match } from '../types'
import { Trophy, MapPin, Calendar } from 'lucide-react'

interface LiveMatchCardProps {
  match: Match | null
  isCompleted: boolean
}

const LiveMatchCardComponent = ({ match, isCompleted }: LiveMatchCardProps) => {
  // Trigger confetti when match completes
  useEffect(() => {
    if (isCompleted && match) {
      const duration = 2000
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
        confetti({
          ...defaults,
          particleCount,
          origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 },
        })
        confetti({
          ...defaults,
          particleCount,
          origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 },
        })
      }, 250)
    }
  }, [isCompleted, match])

  const homeWinProb = match?.home_win_probability || 50
  const awayWinProb = match?.away_win_probability || 50
  const prediction = match?.prediction_data

  return (
    <AnimatePresence mode="wait">
      {match ? (
        <motion.div
          key={match.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          style={{ willChange: 'transform, opacity' }}
          className="w-full"
        >
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Match Details</h2>
        
        <div className="space-y-3 mb-6">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-600 flex items-center gap-1">
              <MapPin className="h-4 w-4" />
              Venue
            </span>
            <span className="font-semibold text-slate-900">{match.venue_name}</span>
          </div>
          
          {prediction?.toss_winner && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Toss Winner</span>
              <span className="font-semibold text-slate-900">
                {prediction.toss_winner === 'home' ? match.home_team_name : match.away_team_name}
              </span>
            </div>
          )}
          
          {prediction?.bat_first && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Batted First</span>
              <span className="font-semibold text-slate-900">
                {prediction.bat_first === 'home' ? match.home_team_name : match.away_team_name}
              </span>
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-slate-200 mb-6">
          <div className="text-center">
            <div className="text-lg font-bold text-slate-900 mb-1">{match.home_team_name}</div>
            <div className="text-sm text-slate-500 mb-1">vs</div>
            <div className="text-lg font-bold text-slate-900">{match.away_team_name}</div>
          </div>
        </div>

        {!isCompleted ? (
          <>
            {/* Win Probability */}
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-600">{match.home_team_name}</span>
                  <span className="font-semibold text-slate-900">{homeWinProb.toFixed(1)}%</span>
                </div>
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-emerald-500 to-emerald-600"
                    initial={{ width: 0 }}
                    animate={{ width: `${homeWinProb}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                  />
                </div>
              </div>
              
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-600">{match.away_team_name}</span>
                  <span className="font-semibold text-slate-900">{awayWinProb.toFixed(1)}%</span>
                </div>
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-blue-500 to-blue-600"
                    initial={{ width: 0 }}
                    animate={{ width: `${awayWinProb}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                  />
                </div>
              </div>
            </div>

            {/* Predicted Scores */}
            {prediction?.predicted_scores && (
              <motion.div 
                className="mt-6 space-y-4"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.3 }}
              >
                <motion.div 
                  className="rounded-lg border border-slate-200 bg-slate-50 p-4"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.3, duration: 0.3 }}
                >
                  <div className="text-xs text-slate-500 mb-1">First Innings</div>
                  <div className="text-sm text-slate-600 mb-1">{prediction.predicted_scores.first_team}</div>
                  <div className="text-2xl font-bold text-slate-900">
                    {prediction.predicted_scores.first_innings_score}/{prediction.predicted_scores.first_innings_wickets}
                  </div>
                </motion.div>
                <motion.div 
                  className="rounded-lg border border-slate-200 bg-slate-50 p-4"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.4, duration: 0.3 }}
                >
                  <div className="text-xs text-slate-500 mb-1">Second Innings</div>
                  <div className="text-sm text-slate-600 mb-1">{prediction.predicted_scores.second_team}</div>
                  <div className="text-2xl font-bold text-slate-900">
                    {prediction.predicted_scores.second_innings_score}/{prediction.predicted_scores.second_innings_wickets}
                  </div>
                </motion.div>
              </motion.div>
            )}

            {/* Top Performers */}
            {(prediction?.top_3_run_scorers || prediction?.top_3_wicket_takers) && (
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {/* Top Run Scorers */}
                {prediction.top_3_run_scorers && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <h4 className="text-sm font-semibold text-slate-900 mb-3">Top Run Scorers</h4>
                    <div className="space-y-2">
                      {[
                        ...(prediction.top_3_run_scorers.home || []),
                        ...(prediction.top_3_run_scorers.away || [])
                      ].slice(0, 3).map((player, idx) => (
                        <div key={player.player_id} className="flex items-center justify-between text-sm">
                          <span className="text-slate-700">{idx + 1}. {player.player_name}</span>
                          <span className="font-semibold text-slate-900">{player.predicted_runs} runs</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Top Wicket Takers */}
                {prediction.top_3_wicket_takers && (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <h4 className="text-sm font-semibold text-slate-900 mb-3">Top Wicket Takers</h4>
                    <div className="space-y-2">
                      {[
                        ...(prediction.top_3_wicket_takers.home || []),
                        ...(prediction.top_3_wicket_takers.away || [])
                      ].slice(0, 3).map((player, idx) => (
                        <div key={player.player_id} className="flex items-center justify-between text-sm">
                          <span className="text-slate-700">{idx + 1}. {player.player_name}</span>
                          <span className="font-semibold text-slate-900">{player.predicted_wickets} wkts</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <motion.div 
            className="text-center pt-4"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          >
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <Trophy className="w-12 h-12 text-emerald-600 mx-auto mb-3" />
            </motion.div>
            <motion.div 
              className="text-2xl font-bold text-emerald-600 mb-2"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              {match.winner_name} Wins!
            </motion.div>
            {match.home_score !== undefined && match.away_score !== undefined && (
              <div className="text-lg text-slate-600 mt-4 space-y-1">
                <div>{match.home_team_name}: <span className="font-semibold">{match.home_score}</span></div>
                <div>{match.away_team_name}: <span className="font-semibold">{match.away_score}</span></div>
                {match.winner_id && (
                  <div className="text-emerald-600 font-semibold mt-2">
                    {(() => {
                      const margin = Math.abs(match.home_score - match.away_score)
                      const winnerIsHome = match.winner_id === match.home_team_id
                      return `${winnerIsHome ? match.home_team_name : match.away_team_name} won by ${margin} ${margin === 1 ? 'run' : 'runs'}`
                    })()}
                  </div>
                )}
              </div>
            )}
            {prediction?.match_result && (
              <motion.div 
                className="mt-4 text-sm text-slate-500"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
              >
                {prediction.match_result.result_text}
              </motion.div>
            )}
          </motion.div>
        )}
      </div>
    </motion.div>
      ) : (
        <motion.div
          key="no-match"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="rounded-xl border border-slate-200 bg-white p-6 shadow-md"
        >
          <div className="text-center text-slate-400">No match in progress</div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Memoize to prevent unnecessary re-renders
export const LiveMatchCard = React.memo(LiveMatchCardComponent)
