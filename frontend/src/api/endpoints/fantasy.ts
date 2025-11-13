import { apiClient } from '../client'

export interface FantasyProjection {
  player_id: number
  player_name: string
  team_id: number
  role: string
  expected_points: number
  p10: number
  p50: number
  p90: number
  avg_runs: number
  avg_wickets: number
  avg_catches: number
}

export interface OptimizeTeamRequest {
  matchday: string
  budget?: number
  max_per_team?: number
  min_batsmen?: number
  min_bowlers?: number
  min_all_rounders?: number
  min_wicket_keepers?: number
}

export interface OptimizedTeam {
  team: FantasyProjection[]
  captain?: FantasyProjection
  vice_captain?: FantasyProjection
  total_points: number
  total_cost: number
  budget_used: number
  budget_remaining: number
  role_counts: Record<string, number>
  team_counts: Record<number, number>
}

export interface Differential {
  player_id: number
  player_name: string
  team_id: number
  role: string
  expected_points: number
  ownership: number
  value: number
  p10: number
  p50: number
  p90: number
}

export const fantasyAPI = {
  getProjections: (matchday: string, playerIds?: number[]) => {
    const params = new URLSearchParams()
    params.append('matchday', matchday)
    if (playerIds && playerIds.length > 0) {
      playerIds.forEach(id => params.append('player_ids', String(id)))
    }
    return apiClient.get<FantasyProjection[]>(`/fantasy/projections?${params.toString()}`)
  },

  optimizeTeam: (request: OptimizeTeamRequest) =>
    apiClient.post<OptimizedTeam>('/fantasy/optimize', request),

  getDifferentials: (params?: {
    matchday: string
    max_ownership?: number
    min_expected_points?: number
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params?.matchday) search.append('matchday', params.matchday)
    if (params?.max_ownership !== undefined) search.append('max_ownership', String(params.max_ownership))
    if (params?.min_expected_points !== undefined) search.append('min_expected_points', String(params.min_expected_points))
    if (params?.limit !== undefined) search.append('limit', String(params.limit))
    const query = search.toString()
    return apiClient.get<Differential[]>(`/fantasy/differentials${query ? `?${query}` : ''}`)
  }
}

