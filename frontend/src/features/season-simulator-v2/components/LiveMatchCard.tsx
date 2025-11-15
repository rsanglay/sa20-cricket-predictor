import React, { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect } from 'react'
import confetti from 'canvas-confetti'
import { Match } from '../types'
import { Trophy, MapPin, Calendar } from 'lucide-react'

interface LiveMatchCardProps {
  match: Match | null
  isCompleted: boolean
  allMatches?: Match[] // Optional: pass all matches to find latest version
}

const LiveMatchCardComponent = ({ match, isCompleted, allMatches }: LiveMatchCardProps) => {
  // CRITICAL: If allMatches is provided, find the latest version of this match
  // This ensures we always have the result if it exists in the matches array
  const latestMatch = useMemo(() => {
    if (!match || !match.id || !allMatches) return match
    const matchFromArray = allMatches.find(m => m.id === match.id)
    return matchFromArray || match
  }, [match, allMatches])
  
  // Use latestMatch instead of match for all checks
  const displayMatch = latestMatch || match
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

  const homeWinProb = displayMatch?.home_win_probability || 50
  const awayWinProb = displayMatch?.away_win_probability || 50
  const prediction = displayMatch?.prediction_data
  
  // Check if we have a valid result (with actual innings data, not just toss)
  // A valid result must have both innings with runs > 0
  const hasValidResult = displayMatch?.result && 
    displayMatch.result.first_innings && 
    displayMatch.result.second_innings &&
    typeof displayMatch.result.first_innings.runs === 'number' &&
    typeof displayMatch.result.second_innings.runs === 'number' &&
    displayMatch.result.first_innings.runs > 0 && 
    displayMatch.result.second_innings.runs > 0
  
  // Show result if match is completed OR if we have a valid result (even if not yet marked as completed)
  const shouldShowResult = isCompleted || hasValidResult
  
  // Debug logging
  if (displayMatch && process.env.NODE_ENV === 'development') {
    console.log('[LiveMatchCard] Match state:', {
      id: displayMatch.id,
      completed: displayMatch.completed,
      hasResult: !!displayMatch.result,
      hasValidResult,
      firstInningsRuns: displayMatch.result?.first_innings?.runs,
      secondInningsRuns: displayMatch.result?.second_innings?.runs,
      shouldShowResult,
      matchFromArray: latestMatch?.id !== match?.id ? 'YES' : 'NO',
    })
  }

  return (
    <AnimatePresence mode="wait">
      {displayMatch ? (
        <motion.div
          key={displayMatch.id}
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
            <span className="font-semibold text-slate-900">{displayMatch.venue_name}</span>
          </div>
          
          {(displayMatch.result?.toss_winner_id || prediction?.toss_winner) && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Toss Winner</span>
              <span className="font-semibold text-slate-900">
                {displayMatch.result?.toss_winner_id 
                  ? (displayMatch.result.toss_winner_id === displayMatch.home_team_id ? displayMatch.home_team_name : displayMatch.away_team_name)
                  : (prediction?.toss_winner === 'home' ? displayMatch.home_team_name : displayMatch.away_team_name)}
              </span>
            </div>
          )}
          
          {displayMatch.result?.toss_decision && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Batted First</span>
              <span className="font-semibold text-slate-900">
                {displayMatch.result.toss_decision === 'bat'
                  ? (displayMatch.result.toss_winner_id === displayMatch.home_team_id ? displayMatch.home_team_name : displayMatch.away_team_name)
                  : (displayMatch.result.toss_winner_id === displayMatch.home_team_id ? displayMatch.away_team_name : displayMatch.home_team_name)}
              </span>
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-slate-200 mb-6">
          <div className="text-center">
            <div className="text-lg font-bold text-slate-900 mb-1">{displayMatch.home_team_name}</div>
            <div className="text-sm text-slate-500 mb-1">vs</div>
            <div className="text-lg font-bold text-slate-900">{displayMatch.away_team_name}</div>
          </div>
        </div>

        {!shouldShowResult ? (
          <>
            {/* Win Probability */}
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-slate-600">{displayMatch.home_team_name}</span>
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
                  <span className="text-slate-600">{displayMatch.away_team_name}</span>
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

            {/* Show actual result if available, otherwise show predicted scores */}
            {/* CRITICAL: Always prefer result over predicted scores if result exists */}
            {/* Check for result in multiple ways to ensure we catch it */}
            {hasValidResult && displayMatch.result ? (
              // Show actual result (same format as completed match)
              <div className="mt-6 space-y-4">
                <div className="text-center mb-4">
                  <span className="text-sm font-medium text-gray-500">MATCH RESULT</span>
                </div>
                <div className="space-y-4">
                  {/* First Innings */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="font-semibold text-slate-900">
                        {displayMatch.result.first_innings.team_id === displayMatch.home_team_id 
                          ? displayMatch.home_team_name 
                          : displayMatch.away_team_name}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900">
                        {displayMatch.result.first_innings.runs}/{displayMatch.result.first_innings.wickets}
                      </div>
                      <div className="text-sm text-gray-600">
                        ({displayMatch.result.first_innings.overs} overs)
                      </div>
                    </div>
                  </div>
                  {/* Second Innings */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="font-semibold text-slate-900">
                        {displayMatch.result.second_innings.team_id === displayMatch.home_team_id 
                          ? displayMatch.home_team_name 
                          : displayMatch.away_team_name}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900">
                        {displayMatch.result.second_innings.runs}/{displayMatch.result.second_innings.wickets}
                      </div>
                      <div className="text-sm text-gray-600">
                        ({displayMatch.result.second_innings.overs} overs)
                      </div>
                    </div>
                  </div>
                </div>
                {/* Show winner if available */}
                {displayMatch.winner_name && (
                  <div className="mt-4 pt-4 border-t text-center">
                    <div className="text-emerald-600 font-bold text-lg">
                      {displayMatch.winner_name} won by {displayMatch.result.margin}
                    </div>
                  </div>
                )}
              </div>
            ) : prediction?.predicted_scores ? (
              // Show predicted scores only if no result exists yet
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
                  <div className="text-xs text-slate-500 mb-1">First Innings (Predicted)</div>
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
                  <div className="text-xs text-slate-500 mb-1">Second Innings (Predicted)</div>
                  <div className="text-sm text-slate-600 mb-1">{prediction.predicted_scores.second_team}</div>
                  <div className="text-2xl font-bold text-slate-900">
                    {prediction.predicted_scores.second_innings_score}/{prediction.predicted_scores.second_innings_wickets}
                  </div>
                </motion.div>
              </motion.div>
            ) : null}

            {/* Top Performers */}
            {(prediction?.top_3_run_scorers || prediction?.top_3_wicket_takers) && displayMatch && (
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
            {hasValidResult && (
              <>
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
                  {displayMatch.winner_name || (displayMatch.result && displayMatch.result.winner_id === displayMatch.home_team_id ? displayMatch.home_team_name : displayMatch.away_team_name)} Wins!
                </motion.div>
              </>
            )}
            {displayMatch.result && hasValidResult ? (
              // Show complete match result with innings data
              <div className="mt-6 space-y-4">
                <div className="text-center mb-4">
                  <span className="text-sm font-medium text-gray-500">MATCH RESULT</span>
                </div>
                <div className="space-y-4">
                  {/* First Innings */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="font-semibold text-slate-900">
                        {displayMatch.result.first_innings.team_id === displayMatch.home_team_id 
                          ? displayMatch.home_team_name 
                          : displayMatch.away_team_name}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900">
                        {displayMatch.result.first_innings.runs}/{displayMatch.result.first_innings.wickets}
                      </div>
                      <div className="text-sm text-gray-600">
                        ({displayMatch.result.first_innings.overs} overs)
                      </div>
                    </div>
                  </div>
                  {/* Second Innings */}
                  <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <span className="font-semibold text-slate-900">
                        {displayMatch.result.second_innings.team_id === displayMatch.home_team_id 
                          ? displayMatch.home_team_name 
                          : displayMatch.away_team_name}
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-slate-900">
                        {displayMatch.result.second_innings.runs}/{displayMatch.result.second_innings.wickets}
                      </div>
                      <div className="text-sm text-gray-600">
                        ({displayMatch.result.second_innings.overs} overs)
                      </div>
                    </div>
                  </div>
                </div>
                {/* Winner announcement */}
                <div className="mt-6 pt-6 border-t text-center">
                  <div className="text-emerald-600 font-bold text-lg">
                    {displayMatch.winner_name} won by {displayMatch.result.margin}
                  </div>
                </div>
              </div>
            ) : (
              // Fallback to legacy scores if result not available
              displayMatch.home_score !== undefined && displayMatch.away_score !== undefined && (
                <div className="text-lg text-slate-600 mt-4 space-y-1">
                  <div>{displayMatch.home_team_name}: <span className="font-semibold">{displayMatch.home_score}</span></div>
                  <div>{displayMatch.away_team_name}: <span className="font-semibold">{displayMatch.away_score}</span></div>
                  {displayMatch.winner_id && (
                    <div className="text-emerald-600 font-semibold mt-2">
                      {(() => {
                        const margin = Math.abs(displayMatch.home_score - displayMatch.away_score)
                        const winnerIsHome = displayMatch.winner_id === displayMatch.home_team_id
                        return `${winnerIsHome ? displayMatch.home_team_name : displayMatch.away_team_name} won by ${margin} ${margin === 1 ? 'run' : 'runs'}`
                      })()}
                    </div>
                  )}
                </div>
              )
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

