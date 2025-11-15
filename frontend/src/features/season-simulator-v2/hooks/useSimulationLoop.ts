import { useEffect, useRef, useCallback, useMemo } from 'react'
import { useSimulationStore } from '../store/simulationStore'
import { Match, Standing, TopPerformers } from '../types'
import { predictionsAPI } from '../../../api/endpoints/predictions'
import { playersAPI } from '../../../api/endpoints/players'
import { teamsAPI } from '../../../api/endpoints/teams'
import { generateRealisticMatchResult } from '../utils/matchResultGenerator'

interface TeamStats {
  wins: number
  losses: number
  no_result: number
  matches: number
  runs_scored: number
  runs_conceded: number
  overs_faced: number
  overs_bowled: number
}

export const useSimulationLoop = () => {
  const {
    phase,
    matches,
    currentMatchIndex,
    isPlaying,
    isPaused,
    speedMultiplier,
    setCurrentMatch,
    setCurrentMatchIndex,
    setStandings,
    setPlayoffTeams,
    setChampion,
    setTopPerformers,
    updateMatchComplete,
    startPreMatchSequence,
    setPreMatchStage,
    completePreMatchSequence,
    setIsPreparingMatch,
  } = useSimulationStore()

  const isProcessingRef = useRef(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const animationFrameRef = useRef<number | null>(null)

  // Memoize current match to prevent unnecessary re-renders
  const currentMatch = useMemo(() => {
    const match = matches[currentMatchIndex] || null
    // Ensure currentMatch in store is synced
    if (match && useSimulationStore.getState().currentMatch?.id !== match.id) {
      useSimulationStore.getState().setCurrentMatch(match)
    }
    return match
  }, [matches, currentMatchIndex])

  // Smooth transition helper
  const requestAnimationFrameUpdate = useCallback(async (callback: () => void | Promise<void>) => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }
    return new Promise<void>((resolve) => {
      animationFrameRef.current = requestAnimationFrame(async () => {
        await callback()
        animationFrameRef.current = null
        resolve()
      })
    })
  }, [])

  // Define updateStandings BEFORE useEffect that uses it
  const updateStandings = useCallback((updatedMatches: Match[]) => {
    const completedMatches = updatedMatches.filter(m => m.completed && m.match_type === 'league')
    const teamStats = new Map<number, TeamStats>()

    // Get current standings from store (always use latest)
    const currentStandings = useSimulationStore.getState().standings
    
    // If standings are empty, derive teams from matches
    if (currentStandings.length === 0) {
      // Extract unique team IDs from all matches
      const teamIds = new Set<number>()
      updatedMatches.forEach(match => {
        teamIds.add(match.home_team_id)
        teamIds.add(match.away_team_id)
      })
      
      // Initialize standings from teams found in matches
      Array.from(teamIds).forEach(teamId => {
        const match = updatedMatches.find(m => m.home_team_id === teamId || m.away_team_id === teamId)
        const teamName = match?.home_team_id === teamId ? match.home_team_name : match?.away_team_name || `Team ${teamId}`
        teamStats.set(teamId, {
          wins: 0,
          losses: 0,
          no_result: 0,
          matches: 0,
          runs_scored: 0,
          runs_conceded: 0,
          overs_faced: 0,
          overs_bowled: 0,
        })
      })
    } else {
      // Initialize from current standings
      currentStandings.forEach(standing => {
        teamStats.set(standing.team_id, {
          wins: 0,
          losses: 0,
          no_result: 0,
          matches: 0,
          runs_scored: 0,
          runs_conceded: 0,
          overs_faced: 0,
          overs_bowled: 0,
        })
      })
    }

    // Process completed matches
    completedMatches.forEach(match => {
      const homeStats = teamStats.get(match.home_team_id)!
      const awayStats = teamStats.get(match.away_team_id)!

      homeStats.matches++
      awayStats.matches++

      // Track runs (assuming 20 overs per innings for T20)
      const oversPerInnings = 20
      if (match.home_score !== undefined) {
        homeStats.runs_scored += match.home_score
        homeStats.overs_faced += oversPerInnings
        awayStats.runs_conceded += match.home_score
        awayStats.overs_bowled += oversPerInnings
      }
      if (match.away_score !== undefined) {
        awayStats.runs_scored += match.away_score
        awayStats.overs_faced += oversPerInnings
        homeStats.runs_conceded += match.away_score
        homeStats.overs_bowled += oversPerInnings
      }

      if (match.no_result) {
        homeStats.no_result++
        awayStats.no_result++
      } else if (match.winner_id) {
        if (match.winner_id === match.home_team_id) {
          homeStats.wins++
          awayStats.losses++
        } else {
          awayStats.wins++
          homeStats.losses++
        }
      }

      teamStats.set(match.home_team_id, homeStats)
      teamStats.set(match.away_team_id, awayStats)
    })

    // Calculate standings with NRR
    // If currentStandings is empty, create new standings from teamStats
    let updatedStandings: Standing[]
    if (currentStandings.length === 0) {
      // Create standings from teamStats
      updatedStandings = Array.from(teamStats.entries()).map(([teamId, stats]) => {
        const match = updatedMatches.find(m => m.home_team_id === teamId || m.away_team_id === teamId)
        const teamName = match?.home_team_id === teamId ? match.home_team_name : match?.away_team_name || `Team ${teamId}`
        
        const runRateFor = stats.overs_faced > 0 ? stats.runs_scored / stats.overs_faced : 0
        const runRateAgainst = stats.overs_bowled > 0 ? stats.runs_conceded / stats.overs_bowled : 0
        const netRunRate = runRateFor - runRateAgainst
        const points = stats.wins * 2 + stats.no_result * 1

        return {
          team_id: teamId,
          team_name: teamName,
          position: 0, // Will be set after sorting
          matches_played: stats.matches,
          wins: stats.wins,
          losses: stats.losses,
          no_result: stats.no_result,
          points: points,
          net_run_rate: netRunRate,
          playoff_probability: 0,
          championship_probability: 0,
        }
      })
    } else {
      // Update existing standings
      updatedStandings = currentStandings.map(standing => {
        const stats = teamStats.get(standing.team_id)
        if (stats) {
          // Calculate Net Run Rate: (runs scored / overs faced) - (runs conceded / overs bowled)
          const runRateFor = stats.overs_faced > 0 ? stats.runs_scored / stats.overs_faced : 0
          const runRateAgainst = stats.overs_bowled > 0 ? stats.runs_conceded / stats.overs_bowled : 0
          const netRunRate = runRateFor - runRateAgainst

          // Points: win = 2, no result = 1, loss = 0
          const points = stats.wins * 2 + stats.no_result * 1

          return {
            ...standing,
            matches_played: stats.matches,
            wins: stats.wins,
            losses: stats.losses,
            no_result: stats.no_result,
            points: points,
            net_run_rate: netRunRate,
          }
        }
        return standing
      })
    }

    // Sort by points (desc), then NRR (desc), then wins (desc)
    updatedStandings.sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points
      if (b.net_run_rate !== a.net_run_rate) return b.net_run_rate - a.net_run_rate
      return b.wins - a.wins
    })

    // Update positions
    updatedStandings.forEach((s, index) => {
      s.position = index + 1
    })

    return updatedStandings
  }, [])

  // Define updateTopPerformers BEFORE useEffect that uses it
  const updateTopPerformers = useCallback((prediction: any, allMatches: Match[]): TopPerformers => {
    // Track player stats across all matches
    const playerStats = new Map<number, { runs: number; wickets: number; player_name: string; team_name?: string; player_id: number }>()
    
    // Aggregate stats from all completed matches
    allMatches.filter(m => m.completed && m.prediction_data).forEach(match => {
      const pred = match.prediction_data
      
      // Add runs from top scorers
      if (pred.top_3_run_scorers) {
        const allScorers = [
          ...(pred.top_3_run_scorers.home || []),
          ...(pred.top_3_run_scorers.away || [])
        ]
        allScorers.forEach(player => {
          const existing = playerStats.get(player.player_id)
          if (existing) {
            existing.runs += player.predicted_runs || 0
          } else {
            playerStats.set(player.player_id, {
              player_id: player.player_id,
              runs: player.predicted_runs || 0,
              wickets: 0,
              player_name: player.player_name,
              team_name: player.team_name,
            })
          }
        })
      }
      
      // Add wickets from top wicket takers
      if (pred.top_3_wicket_takers) {
        const allBowlers = [
          ...(pred.top_3_wicket_takers.home || []),
          ...(pred.top_3_wicket_takers.away || [])
        ]
        allBowlers.forEach(player => {
          const existing = playerStats.get(player.player_id)
          if (existing) {
            existing.wickets += player.predicted_wickets || 0
          } else {
            playerStats.set(player.player_id, {
              player_id: player.player_id,
              runs: 0,
              wickets: player.predicted_wickets || 0,
              player_name: player.player_name,
              team_name: player.team_name,
            })
          }
        })
      }
    })
    
    // Find top performers
    const allPlayers = Array.from(playerStats.values())
    const topRunScorer = allPlayers.length > 0 
      ? allPlayers.reduce((max, p) => p.runs > max.runs ? p : max, allPlayers[0])
      : null
    const topWicketTaker = allPlayers.length > 0
      ? allPlayers.reduce((max, p) => p.wickets > max.wickets ? p : max, allPlayers[0])
      : null
    
    // Calculate MVP (combination of runs and wickets)
    let mvp = null
    if (allPlayers.length > 0) {
      mvp = allPlayers.reduce((best, p) => {
        const score = p.runs + (p.wickets * 25) // Weight wickets more
        const bestScore = best.runs + (best.wickets * 25)
        return score > bestScore ? p : best
      }, allPlayers[0])
    }
    
    return {
      orangeCap: topRunScorer ? {
        player_id: topRunScorer.player_id,
        player_name: topRunScorer.player_name,
        team_name: topRunScorer.team_name,
        runs: topRunScorer.runs,
      } : null,
      purpleCap: topWicketTaker ? {
        player_id: topWicketTaker.player_id,
        player_name: topWicketTaker.player_name,
        team_name: topWicketTaker.team_name,
        wickets: topWicketTaker.wickets,
      } : null,
      mvp: mvp ? {
        player_id: mvp.player_id,
        player_name: mvp.player_name,
        team_name: mvp.team_name,
        runs: mvp.runs,
        wickets: mvp.wickets,
        score: mvp.runs + (mvp.wickets * 25),
      } : null,
    }
  }, [])

  // Define determinePlayoffTeams BEFORE useEffect that uses it
  const determinePlayoffTeams = useCallback(() => {
    const currentStandings = useSimulationStore.getState().standings
    const top4 = currentStandings.slice(0, 4)
    setPlayoffTeams(top4.map(s => ({ id: s.team_id, name: s.team_name, short_name: s.team_name })))
    
    // Calculate final top performers
    const allMatches = useSimulationStore.getState().matches
    const completedMatches = allMatches.filter(m => m.completed && m.prediction_data)
    if (completedMatches.length > 0) {
      // Use the last match's prediction to get final stats (or aggregate all)
      const lastMatch = completedMatches[completedMatches.length - 1]
      if (lastMatch.prediction_data) {
        updateTopPerformers(lastMatch.prediction_data, allMatches)
      }
    }
  }, [setPlayoffTeams, updateTopPerformers])

  useEffect(() => {
    // Cleanup on unmount or phase change
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
        animationFrameRef.current = null
      }
      isProcessingRef.current = false
    }
  }, [phase])

  // Helper to preload images
  const preloadImage = useCallback((url: string): Promise<void> => {
    return new Promise((resolve) => {
      const img = new Image()
      img.onload = () => resolve()
      img.onerror = () => resolve() // Don't block on error
      img.src = url
      setTimeout(resolve, 2000) // Timeout after 2 seconds
    })
  }, [])

  // Helper to wait (respects speed multiplier)
  const wait = useCallback((ms: number) => {
    return new Promise(resolve => setTimeout(resolve, ms / speedMultiplier))
  }, [speedMultiplier])

  // Run pre-match sequence with proper staging
  const runPreMatchSequence = useCallback(async (match: Match) => {
    console.log('[PreMatch] Starting sequence for match', match.id)
    
    // Stage 1: Toss (3 seconds)
    console.log('[PreMatch] Stage: toss')
    setPreMatchStage('toss')
    await wait(3000)
    
    // Stage 2: Team 1 lineup (3 seconds)
    console.log('[PreMatch] Stage: lineup-team1')
    setPreMatchStage('lineup-team1')
    await wait(3000)
    
    // Stage 3: Team 2 lineup (3 seconds)
    console.log('[PreMatch] Stage: lineup-team2')
    setPreMatchStage('lineup-team2')
    await wait(3000)
    
    // Stage 4: Fade out overlay (500ms)
    console.log('[PreMatch] Stage: complete')
    setPreMatchStage('complete')
    await wait(500)
    
    // Hide overlay - now match card is visible underneath
    completePreMatchSequence()
    console.log('[PreMatch] Sequence complete, starting match')
  }, [setPreMatchStage, completePreMatchSequence, wait])

  // Prepare match: fetch prediction and preload images
  const prepareMatch = useCallback(async (match: Match): Promise<Match> => {
    console.log('[PreMatch] Preparing match', match.id)
    setIsPreparingMatch(true)
    
    try {
      // 1. Fetch prediction data
      const prediction = await predictionsAPI.predictMatch(
        match.home_team_id,
        match.away_team_id,
        match.venue_id
      )
      
      // Generate deterministic toss result (same seed as match completion)
      const seed = match.id
      let seedState = seed
      const seededRandom = () => {
        seedState = ((seedState * 9301) + 49297) % 233280
        return seedState / 233280
      }
      
      // Determine toss winner (50/50) and decision (60% bat first)
      const tossWinner = seededRandom() < 0.5 ? 'home' : 'away'
      const tossDecision = seededRandom() < 0.6 ? 'bat' : 'bowl'
      
      // Create partial result with toss data (will be completed when match finishes)
      const partialResult: Match['result'] = {
        winner_id: 0, // Will be set when match completes
        margin: '', // Will be set when match completes
        first_innings: {
          team_id: 0,
          runs: 0,
          wickets: 0,
          overs: 0,
        },
        second_innings: {
          team_id: 0,
          runs: 0,
          wickets: 0,
          overs: 0,
        },
        toss_winner_id: tossWinner === 'home' ? match.home_team_id : match.away_team_id,
        toss_decision: tossDecision,
      }
      
      // Update match with prediction data and toss result
      const updatedMatch: Match = {
        ...match,
        prediction_data: prediction,
        toss_winner: tossWinner, // Keep for backward compatibility
        bat_first: tossDecision === 'bat' ? tossWinner : (tossWinner === 'home' ? 'away' : 'home'), // Keep for backward compatibility
        home_win_probability: prediction.home_win_probability,
        away_win_probability: prediction.away_win_probability,
        result: partialResult, // Store toss result early for TossAnimation
      }
      
      // 2. Fetch player images and add to lineup data
      const allPlayers = [
        ...(prediction.predicted_starting_xi?.home || []),
        ...(prediction.predicted_starting_xi?.away || [])
      ]
      
      // Fetch all players to get their images
      try {
        const playersData = await playersAPI.getAll({ onlyWithImages: true })
        const playersMap = new Map(playersData.map((p: any) => [p.id, p]))
        
        // Add image_url to lineup players
        const homeLineup = (prediction.predicted_starting_xi?.home || []).map((player: any) => {
          const playerData = playersMap.get(player.player_id) as any
          return {
            ...player,
            image_url: playerData?.image_url
          }
        })
        const awayLineup = (prediction.predicted_starting_xi?.away || []).map((player: any) => {
          const playerData = playersMap.get(player.player_id) as any
          return {
            ...player,
            image_url: playerData?.image_url
          }
        })
        
        // Update prediction with image URLs
        prediction.predicted_starting_xi = {
          home: homeLineup,
          away: awayLineup
        }
        
        // Pre-load all player images
        const imageUrls = [
          ...homeLineup.map((p: any) => p.image_url),
          ...awayLineup.map((p: any) => p.image_url)
        ].filter(Boolean) as string[]
        
        await Promise.all(imageUrls.map(url => preloadImage(url)))
      } catch (error) {
        console.warn('[PreMatch] Could not fetch player images:', error)
        // Continue without images
      }
      
      setIsPreparingMatch(false)
      
      // 3. Update store with match that has prediction data BEFORE showing overlay
      const latestMatches = useSimulationStore.getState().matches
      const latestIndex = useSimulationStore.getState().currentMatchIndex
      const updatedMatches = [...latestMatches]
      updatedMatches[latestIndex] = updatedMatch
      useSimulationStore.getState().setMatches(updatedMatches)
      useSimulationStore.getState().setCurrentMatch(updatedMatch)
      
      console.log('[PreMatch] Match updated in store, prediction_data:', !!updatedMatch.prediction_data)
      
      // 4. NOW show pre-match sequence (everything is ready)
      startPreMatchSequence()
      console.log('[PreMatch] Overlay should be visible now')
      await runPreMatchSequence(updatedMatch)
      
      return updatedMatch
    } catch (error) {
      console.error('[PreMatch] Error preparing match:', error)
      setIsPreparingMatch(false)
      // Return match without prediction data - will skip pre-match
      return match
    }
  }, [preloadImage, setIsPreparingMatch, startPreMatchSequence, runPreMatchSequence])

  useEffect(() => {
    // Only run in LEAGUE phase
    if (phase !== 'LEAGUE' || matches.length === 0) {
      return
    }

    // Ensure current match is set from matches array
    const matchFromArray = matches[currentMatchIndex]
    if (matchFromArray && (!currentMatch || currentMatch.id !== matchFromArray.id)) {
      console.log('[PreMatch] Setting current match from array:', matchFromArray.id)
      useSimulationStore.getState().setCurrentMatch(matchFromArray)
    }

    // Check if current match needs preparation (no prediction_data and not completed)
    const matchToCheck = matchFromArray || currentMatch
    if (matchToCheck && !matchToCheck.completed && !matchToCheck.prediction_data && !isProcessingRef.current) {
      console.log('[PreMatch] Match needs preparation:', matchToCheck.id, 'isPlaying:', isPlaying, 'isPaused:', isPaused)
      
      // Always prepare match, even if paused (overlay can still show)
      isProcessingRef.current = true
      prepareMatch(matchToCheck).then(updatedMatch => {
        // Get latest matches from store to avoid stale closure
        const latestMatches = useSimulationStore.getState().matches
        const latestIndex = useSimulationStore.getState().currentMatchIndex
        
        // Only update if match is not completed (preserve completed matches)
        const existingMatch = latestMatches[latestIndex]
        if (existingMatch?.completed) {
          console.warn('[PreMatch] Match already completed, skipping prediction update:', existingMatch.id)
          isProcessingRef.current = false
          return
        }
        
        const updatedMatches = [...latestMatches]
        updatedMatches[latestIndex] = updatedMatch
        useSimulationStore.getState().setMatches(updatedMatches)
        useSimulationStore.getState().setCurrentMatch(updatedMatch)
        isProcessingRef.current = false
        console.log('[PreMatch] Match prepared successfully:', updatedMatch.id)
      }).catch(error => {
        console.error('[PreMatch] Error in prepareMatch:', error)
        isProcessingRef.current = false
      })
      
      // If paused or not playing, return here (overlay will show but simulation won't start)
      if (!isPlaying || isPaused) {
        return
      }
    }

    // If paused or not playing, don't continue with simulation
    if (!isPlaying || isPaused) {
      return
    }

    if (isProcessingRef.current) {
      return
    }

    // Calculate match duration based on speed - make it slower
    const baseDuration = 15000 // 15 seconds per match at 1x
    const matchDuration = baseDuration / speedMultiplier

    // Simulate current match
    const matchToSimulate = matches[currentMatchIndex] || currentMatch
    if (matchToSimulate && !matchToSimulate.completed) {
      // If match doesn't have prediction data, prepare it (fetch + preload + show overlay)
      if (!matchToSimulate.prediction_data) {
        console.log('[PreMatch] Match needs preparation, calling prepareMatch')
        isProcessingRef.current = true
        
        prepareMatch(matchToSimulate).then(updatedMatch => {
          // Get latest matches from store to avoid stale closure
          const latestMatches = useSimulationStore.getState().matches
          const latestIndex = useSimulationStore.getState().currentMatchIndex
          
          // Only update if match is not completed (preserve completed matches)
          const existingMatch = latestMatches[latestIndex]
          if (existingMatch?.completed) {
            console.warn('[PreMatch] Match already completed, skipping prediction update:', existingMatch.id)
            isProcessingRef.current = false
            return
          }
          
          // Update matches array with prediction data
          const updatedMatches = [...latestMatches]
          updatedMatches[latestIndex] = updatedMatch
          useSimulationStore.getState().setMatches(updatedMatches)
          useSimulationStore.getState().setCurrentMatch(updatedMatch)
          
          isProcessingRef.current = false
          
          // Match simulation will start automatically after overlay completes
        }).catch(error => {
          console.error('[PreMatch] Error in prepareMatch:', error)
          isProcessingRef.current = false
        })
        return
      }
      
      // Update currentMatch reference if needed
      if (matchToSimulate.id !== currentMatch?.id) {
        useSimulationStore.getState().setCurrentMatch(matchToSimulate)
      }
      
      // Match has prediction data - start simulation
      const matchWithPrediction = matchToSimulate
      
      // CRITICAL: Check if match is already completed BEFORE starting simulation
      // Get latest state to check completion status
      const preCheckMatches = useSimulationStore.getState().matches
      const preCheckIndex = useSimulationStore.getState().currentMatchIndex
      const preCheckMatch = preCheckMatches[preCheckIndex]
      
      if (preCheckMatch?.completed) {
        console.log('[Match] Match already completed, skipping simulation:', preCheckMatch.id, 'Winner:', preCheckMatch.winner_name)
        isProcessingRef.current = false
        return
      }
      
      // Verify we're working with the correct match
      if (preCheckMatch && preCheckMatch.id !== matchWithPrediction.id) {
        console.warn('[Match] Match ID mismatch before simulation:', preCheckMatch.id, 'vs', matchWithPrediction.id)
        isProcessingRef.current = false
        return
      }
      
      requestAnimationFrameUpdate(() => {
        setCurrentMatch(matchWithPrediction)
      })
      isProcessingRef.current = true

      // Predict match result after a delay with smooth transition
      timerRef.current = setTimeout(async () => {
        await requestAnimationFrameUpdate(async () => {
          try {
            // CRITICAL: Check completion status FIRST, before any random calculations
            // This prevents recalculating results if match was already completed
            const latestMatches = useSimulationStore.getState().matches
            const latestMatchIndex = useSimulationStore.getState().currentMatchIndex
            const matchToUpdate = latestMatches[latestMatchIndex] || matchWithPrediction
            
            // CRITICAL: If match is already completed, use existing result (don't recalculate)
            if (matchToUpdate.completed) {
              console.log('[Match] Match already completed, using existing result:', matchToUpdate.id, 'Winner:', matchToUpdate.winner_name, 'Score:', matchToUpdate.home_score, 'vs', matchToUpdate.away_score)
              
              // Use existing completed match result
              const existingResult = matchToUpdate
              
              // Update matches array (preserve all completed matches)
              const finalUpdatedMatches = latestMatches.map((m, idx) => {
                if (m.completed) return m
                if (idx === latestMatchIndex && m.id === existingResult.id) return existingResult
                return m
              })
              
              // Calculate standings and top performers with existing result
              const newStandings = updateStandings(finalUpdatedMatches)
              const newTopPerformers = updateTopPerformers(matchToUpdate.prediction_data, finalUpdatedMatches)
              
              const nextMatchIndex = latestMatchIndex < latestMatches.length - 1 
                ? latestMatchIndex + 1 
                : latestMatchIndex
              
              updateMatchComplete({
                standings: newStandings,
                topPerformers: newTopPerformers,
                currentMatchIndex: nextMatchIndex,
                matches: finalUpdatedMatches,
              })
              
              isProcessingRef.current = false
              return
            }
            
            // Verify match ID matches
            if (matchToUpdate.id !== matchWithPrediction.id) {
              console.warn('[Match] Match ID mismatch, skipping update:', matchToUpdate.id, 'vs', matchWithPrediction.id)
              isProcessingRef.current = false
              return
            }
            
            // NOW safe to calculate random results (match is not completed)
            const prediction = matchWithPrediction.prediction_data

            // CRITICAL: Use deterministic random seed based on match ID
            // This ensures the same match always produces the same result, even if callback runs multiple times
            const seed = matchWithPrediction.id
            let seedState = seed
            const seededRandom = () => {
              // Simple seeded random number generator (LCG)
              seedState = ((seedState * 9301) + 49297) % 233280
              return seedState / 233280
            }
            
            // Determine winner based on prediction
            const homeWinProb = prediction.home_win_probability || 50
            const isNoResult = seededRandom() < 0.02 // 2% chance of no result
            let winnerId: number | undefined
            let winnerName: string | undefined
            let noResult = false
            let matchResult: Match['result'] | undefined

            if (isNoResult) {
              noResult = true
              winnerId = undefined
              winnerName = undefined
              matchResult = undefined
            } else {
              // Determine winner first (deterministic based on seed)
              const homeWins = seededRandom() * 100 < homeWinProb
              const determinedWinner = homeWins ? 'home' : 'away'
              winnerId = homeWins
                ? matchWithPrediction.home_team_id
                : matchWithPrediction.away_team_id
              winnerName = homeWins
                ? matchWithPrediction.home_team_name
                : matchWithPrediction.away_team_name

              // Fetch teams data for result generation
              try {
                const teams = await teamsAPI.getAll()
                const homeTeam = teams.find((t: { id: number }) => t.id === matchWithPrediction.home_team_id)
                const awayTeam = teams.find((t: { id: number }) => t.id === matchWithPrediction.away_team_id)

                if (homeTeam && awayTeam) {
                  // Generate realistic match result
                  // Use the same seeded random state to ensure consistency
                  // Reset seed state to match ID (same as in prepareMatch)
                  seedState = seed
                  
                  matchResult = generateRealisticMatchResult({
                    homeTeam: { id: homeTeam.id, name: homeTeam.name, short_name: homeTeam.short_name },
                    awayTeam: { id: awayTeam.id, name: awayTeam.name, short_name: awayTeam.short_name },
                    prediction: {
                      home_win_probability: homeWinProb,
                      away_win_probability: 100 - homeWinProb,
                    },
                    determinedWinner,
                    venue: {
                      id: matchWithPrediction.venue_id,
                      avg_first_innings_score: null, // We'll use default in generator
                    },
                    seededRandom,
                    // Use existing toss result from match preparation
                    existingTossResult: matchToUpdate.result?.toss_winner_id && matchToUpdate.result?.toss_decision
                      ? {
                          toss_winner_id: matchToUpdate.result.toss_winner_id,
                          toss_decision: matchToUpdate.result.toss_decision,
                        }
                      : undefined,
                  })

                  console.log('[Match] Generated match result:', matchResult)
                } else {
                  console.warn('[Match] Could not find teams for result generation')
                }
              } catch (error) {
                console.error('[Match] Error fetching teams for result generation:', error)
              }
            }
            
            console.log('[Match] Calculated deterministic result for match:', matchWithPrediction.id, 'Winner:', winnerName, 'Result:', matchResult)

            // Update match with result (create immutable copy)
            const updatedMatch: Match = {
              ...matchToUpdate,
              completed: true,
              winner_id: winnerId,
              winner_name: winnerName,
              // Keep legacy scores for backward compatibility, but prefer result
              home_score: matchResult 
                ? (matchResult.first_innings.team_id === matchWithPrediction.home_team_id 
                    ? matchResult.first_innings.runs 
                    : matchResult.second_innings.runs)
                : undefined,
              away_score: matchResult
                ? (matchResult.first_innings.team_id === matchWithPrediction.away_team_id
                    ? matchResult.first_innings.runs
                    : matchResult.second_innings.runs)
                : undefined,
              no_result: noResult,
              result: matchResult,
            }
            
            console.log('[Match] Completing match:', updatedMatch.id, 'Winner:', updatedMatch.winner_name, 'Score:', updatedMatch.home_score, 'vs', updatedMatch.away_score)

            // Wait for match card exit animation to complete (300ms)
            await new Promise(resolve => setTimeout(resolve, 300 / speedMultiplier))

            // CRITICAL: Get absolute latest state right before updating to prevent race conditions
            // This ensures we have the most up-to-date matches array
            const finalLatestMatches = useSimulationStore.getState().matches
            
            // Use the original latestMatchIndex (the match we're completing), not currentMatchIndex
            // because currentMatchIndex might have changed if another update happened
            const matchIndexToUpdate = latestMatchIndex
            
            // Double-check: verify match is still not completed (prevent race conditions)
            const finalMatchToUpdate = finalLatestMatches[matchIndexToUpdate]
            if (!finalMatchToUpdate) {
              console.warn('[Match] Match not found at index:', matchIndexToUpdate)
              isProcessingRef.current = false
              return
            }
            
            if (finalMatchToUpdate.completed) {
              console.warn('[Match] Match already completed in final check, skipping update:', finalMatchToUpdate.id, 'Winner:', finalMatchToUpdate.winner_name)
              isProcessingRef.current = false
              return
            }
            
            // Verify we're updating the correct match by ID
            if (finalMatchToUpdate.id !== updatedMatch.id) {
              console.warn('[Match] Match ID mismatch in final check:', finalMatchToUpdate.id, 'vs', updatedMatch.id)
              isProcessingRef.current = false
              return
            }
            
            // Update matches array (preserve ALL completed matches, only update current match)
            const finalUpdatedMatches = finalLatestMatches.map((m, idx) => {
              // CRITICAL: Preserve ALL completed matches (never overwrite)
              if (m.completed) {
                return m
              }
              // Update only the match we're completing (by index and ID check)
              if (idx === matchIndexToUpdate && m.id === updatedMatch.id && !m.completed) {
                return updatedMatch
              }
              // Keep all other incomplete matches as-is
              return m
            })

            // Calculate new standings and top performers using final updated matches
            const newStandings = updateStandings(finalUpdatedMatches)
            const newTopPerformers = updateTopPerformers(prediction, finalUpdatedMatches)
            
            // Calculate next match index (use the index we just updated, not currentMatchIndex)
            const nextMatchIndex = matchIndexToUpdate < finalLatestMatches.length - 1 
              ? matchIndexToUpdate + 1 
              : matchIndexToUpdate
            
            // Batch all updates in one atomic operation
            updateMatchComplete({
              standings: newStandings,
              topPerformers: newTopPerformers,
              currentMatchIndex: nextMatchIndex,
              matches: finalUpdatedMatches,
            })

            isProcessingRef.current = false

            // Wait for standings animation to complete before moving to next match
            // Standings animation duration: 800ms, but respect speed multiplier
            const standingsAnimationDuration = 800 / speedMultiplier
            await new Promise(resolve => setTimeout(resolve, standingsAnimationDuration))

            // Move to next match or qualification phase
            if (latestMatchIndex < latestMatches.length - 1) {
              // After standings animation, the next match will be processed in the next useEffect cycle
              // The useEffect will detect the new match doesn't have prediction_data and call prepareMatch
              // This ensures pre-match overlay shows for every match
            } else {
              // All matches complete, move to qualification
              useSimulationStore.getState().setPhase('QUALIFICATION')
              determinePlayoffTeams()
            }
          } catch (error) {
            console.error('Error predicting match:', error)
            isProcessingRef.current = false
            
            // Get latest matches from store to avoid stale closure - CRITICAL: always get fresh state
            const latestMatches = useSimulationStore.getState().matches
            const latestMatchIndex = useSimulationStore.getState().currentMatchIndex
            const latestMatch = latestMatches[latestMatchIndex] || matchWithPrediction
            
            // CRITICAL: Only update if match is not already completed (prevent overwriting)
            if (latestMatch.completed) {
              console.warn('[Match] Match already completed in error handler, skipping update:', latestMatch.id, 'Current winner:', latestMatch.winner_name)
              return
            }
            
            // Double-check: verify match ID matches
            if (latestMatch.id !== matchWithPrediction.id) {
              console.warn('[Match] Match ID mismatch in error handler:', latestMatch.id, 'vs', matchWithPrediction.id)
              return
            }
            
            // Fallback: use simple random prediction
            const homeWinProb = latestMatch.home_win_probability || 50
            const homeWins = Math.random() * 100 < homeWinProb
            const winnerId = homeWins
              ? latestMatch.home_team_id
              : latestMatch.away_team_id
            const winnerName = homeWins
              ? latestMatch.home_team_name
              : latestMatch.away_team_name

            // Ensure scores match winner
            const baseHomeScore = Math.floor(Math.random() * 50) + 150
            const baseAwayScore = Math.floor(Math.random() * 50) + 150
            const homeScore = homeWins ? baseHomeScore : Math.min(baseAwayScore - 1, baseHomeScore)
            const awayScore = homeWins ? Math.min(baseHomeScore - 1, baseAwayScore) : baseAwayScore

            const updatedMatch: Match = {
              ...latestMatch,
              completed: true,
              winner_id: winnerId,
              winner_name: winnerName,
              home_score: homeScore,
              away_score: awayScore,
            }
            
            console.log('[Match] Completing match (error handler):', updatedMatch.id, 'Winner:', updatedMatch.winner_name, 'Score:', updatedMatch.home_score, 'vs', updatedMatch.away_score)

            // Update matches array (preserve all other matches, especially completed ones)
            const updatedMatches = latestMatches.map((m, idx) => {
              // Preserve all completed matches
              if (m.completed && idx !== latestMatchIndex) {
                return m
              }
              // Update the current match
              if (idx === latestMatchIndex) {
                return updatedMatch
              }
              // Keep other incomplete matches as-is
              return m
            })

            // Calculate new standings and top performers
            const newStandings = updateStandings(updatedMatches)
            const newTopPerformers = updateTopPerformers(null, updatedMatches)
            
            // Calculate next match index
            const nextMatchIndex = latestMatchIndex < latestMatches.length - 1 
              ? latestMatchIndex + 1 
              : latestMatchIndex

            // Wait for match card exit animation
            await new Promise(resolve => setTimeout(resolve, 300 / speedMultiplier))

            // Batch all updates
            updateMatchComplete({
              standings: newStandings,
              topPerformers: newTopPerformers,
              currentMatchIndex: nextMatchIndex,
              matches: updatedMatches,
            })

            isProcessingRef.current = false

            // Wait for standings animation
            const standingsAnimationDuration = 800 / speedMultiplier
            await new Promise(resolve => setTimeout(resolve, standingsAnimationDuration))

            if (latestMatchIndex < latestMatches.length - 1) {
              // Match updated via updateMatchComplete
            } else {
              useSimulationStore.getState().setPhase('QUALIFICATION')
              determinePlayoffTeams()
            }
          }
        })
      }, matchDuration)

      return () => {
        if (timerRef.current) {
          clearTimeout(timerRef.current)
          timerRef.current = null
        }
        isProcessingRef.current = false
      }
    }
  }, [phase, currentMatch, currentMatchIndex, isPlaying, isPaused, speedMultiplier, matches, setCurrentMatch, setCurrentMatchIndex, updateStandings, updateTopPerformers, determinePlayoffTeams, requestAnimationFrameUpdate, prepareMatch])
}
