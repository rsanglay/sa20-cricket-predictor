import { apiClient } from '../client'
import { MatchPrediction, SeasonPrediction, StandingsPrediction } from '../../types/prediction'

export interface TopRunScorerPrediction {
  player_id: number
  player_name: string
  team_id?: number
  team_name?: string
  predicted_runs: number
  role?: string
  country?: string
}

export interface TopWicketTakerPrediction {
  player_id: number
  player_name: string
  team_id?: number
  team_name?: string
  predicted_wickets: number
  role?: string
  country?: string
}

export interface TopPredictionsResponse<T> {
  predictions: T[]
  season: number
  error?: string
}

export const predictionsAPI = {
  predictMatch: (homeTeamId: number, awayTeamId: number, venueId: number) =>
    apiClient.post<MatchPrediction>('/predictions/match', {
      home_team_id: homeTeamId,
      away_team_id: awayTeamId,
      venue_id: venueId
    }),

  simulateSeason: (numSimulations = 1000, customXIs?: Record<number, number[]>) => {
    return apiClient.post<SeasonPrediction>('/predictions/season', {
      num_simulations: numSimulations,
      custom_xis: customXIs || null,
    }, {
      timeout: 120000, // 2 minutes for simulation
    })
  },

  getStandings: () => apiClient.get<StandingsPrediction>('/predictions/standings'),

  getTopRunScorers: (limit = 10) => {
    const params = new URLSearchParams()
    params.append('limit', String(limit))
    return apiClient.get<TopPredictionsResponse<TopRunScorerPrediction>>(`/predictions/top-run-scorer?${params.toString()}`)
  },

  getTopWicketTakers: (limit = 10) => {
    const params = new URLSearchParams()
    params.append('limit', String(limit))
    return apiClient.get<TopPredictionsResponse<TopWicketTakerPrediction>>(`/predictions/top-wicket-taker?${params.toString()}`)
  }
}
