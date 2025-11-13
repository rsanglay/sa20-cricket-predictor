import { useCallback } from 'react'
import { useSimulationStore } from '../store/simulationStore'
import { predictionsAPI } from '../../../api/endpoints/predictions'
import { teamsAPI } from '../../../api/endpoints/teams'
import { matchesAPI, Match as APIMatch } from '../../../api/endpoints/matches'
import { Match, Standing } from '../types'
import { SeasonPrediction } from '../../../types/prediction'
import { Team } from '../../../types/team'

// Convert API Match to simulator Match format
const convertAPIMatchToSimulatorMatch = (apiMatch: APIMatch, teamMap: Map<number, string>, venueMap: Map<number, string>): Match => {
  return {
    id: apiMatch.id,
    match_id: apiMatch.id,
    home_team_id: apiMatch.home_team_id,
    away_team_id: apiMatch.away_team_id,
    venue_id: apiMatch.venue_id,
    home_team_name: apiMatch.home_team_name || teamMap.get(apiMatch.home_team_id) || 'Unknown',
    away_team_name: apiMatch.away_team_name || teamMap.get(apiMatch.away_team_id) || 'Unknown',
    venue_name: apiMatch.venue_name || venueMap.get(apiMatch.venue_id) || 'TBD',
    completed: apiMatch.winner_id !== null && apiMatch.winner_id !== undefined,
    winner_id: apiMatch.winner_id || undefined,
    winner_name: apiMatch.winner_id ? (apiMatch.winner_id === apiMatch.home_team_id ? apiMatch.home_team_name : apiMatch.away_team_name) : undefined,
    match_type: 'league',
    home_win_probability: 50, // Will be updated from simulation data
    away_win_probability: 50,
  }
}

export const useSimulation = () => {
  const {
    phase,
    matches,
    standings,
    currentMatchIndex,
    currentMatch,
    isPlaying,
    isPaused,
    speedMultiplier,
    setPhase,
    setMatches,
    setStandings,
    setCurrentMatch,
    setCurrentMatchIndex,
    setSimulationData,
  } = useSimulationStore()

  const fetchTeamsOnly = useCallback(async () => {
    try {
      // Fetch teams and actual fixtures from database
      const [teams, apiMatches] = await Promise.all([
        teamsAPI.getAll(),
        matchesAPI.getAll({ season: 2026 }) // Get all matches for 2026 season
      ])
      
      if (!teams || !Array.isArray(teams) || teams.length === 0) {
        console.warn('No teams data received, using empty array')
        setMatches([])
        setStandings([])
        return
      }
      
      const teamMap = new Map(teams.map(t => [t.id, t.name]))
      const venueMap = new Map<number, string>() // We'll populate this if venue names are available

      // Store original API matches for sorting
      const originalMatches = apiMatches || []

      // Create a map for O(1) date lookups instead of O(n) finds - much faster!
      const matchDateMap = new Map<number, string>()
      originalMatches.forEach(m => {
        if (m.match_date) matchDateMap.set(m.id, m.match_date)
      })

      // Convert API matches to simulator format
      const simulatorMatches: Match[] = originalMatches.map(apiMatch => 
        convertAPIMatchToSimulatorMatch(apiMatch, teamMap, venueMap)
      )
      
      // Sort matches by date (if available) to ensure correct simulation order
      // Optimized: use map for O(1) lookups instead of O(n) finds
      const sortedMatches = simulatorMatches.sort((a, b) => {
        const dateA = matchDateMap.get(a.id)
        const dateB = matchDateMap.get(b.id)
        if (dateA && dateB) {
          return new Date(dateA).getTime() - new Date(dateB).getTime()
        }
        // Fallback to match ID if dates not available
        return a.id - b.id
      })
      
      // Filter to only league matches (not completed yet, or all if we want to simulate completed ones too)
      const leagueMatches = sortedMatches.filter(m => !m.completed || m.match_type === 'league')
      
      setMatches(leagueMatches.length > 0 ? leagueMatches : sortedMatches)

      // Set initial standings from teams
      const initialStandings: Standing[] = teams.map((team, index) => ({
        team_id: team.id,
        team_name: team.name,
        position: index + 1,
        matches_played: 0,
        wins: 0,
        losses: 0,
        no_result: 0,
        points: 0,
        net_run_rate: 0,
        playoff_probability: 0,
        championship_probability: 0,
      }))
      
      setStandings(initialStandings)
    } catch (error: any) {
      console.error('Failed to fetch teams or matches:', error)
      // Log more details
      if (error.response) {
        console.error('API error:', error.response.status, error.response.data)
      } else if (error.request) {
        console.error('No response from API. Is backend running?')
      }
      // Set empty arrays so UI can still render
      setMatches([])
      setStandings([])
    }
  }, [setMatches, setStandings])

  const fetchSimulationData = useCallback(async (numSimulations = 1) => {
    // We don't need bulk simulations anymore - matches will be predicted individually
    // This function is kept for compatibility but doesn't fetch bulk simulation data
    try {
      // Just ensure teams and matches are loaded
      await fetchTeamsOnly()
    } catch (error: any) {
      console.error('Failed to fetch simulation data:', error)
    }
  }, [fetchTeamsOnly])

  return {
    phase,
    matches,
    standings,
    currentMatch,
    currentMatchIndex,
    isPlaying,
    isPaused,
    speedMultiplier,
    fetchSimulationData,
    fetchTeamsOnly,
    setPhase,
    setCurrentMatch,
    setCurrentMatchIndex,
  }
}

