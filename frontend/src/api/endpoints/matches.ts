import { apiClient } from '../client'

export interface Match {
  id: number
  home_team_id: number
  away_team_id: number
  venue_id: number
  match_date: string
  season: number
  winner_id?: number | null
  margin?: string | null
  match_number?: number | null
  home_team_name?: string
  away_team_name?: string
  venue_name?: string
}

export const matchesAPI = {
  getAll: (params?: { season?: number; teamId?: number; venueId?: number }) => {
    const search = new URLSearchParams()
    if (params?.season) search.append('season', String(params.season))
    if (params?.teamId) search.append('team_id', String(params.teamId))
    if (params?.venueId) search.append('venue_id', String(params.venueId))
    const query = search.toString()
    return apiClient.get<Match[]>(`/matches${query ? `?${query}` : ''}`)
  },

  getUpcoming: (season = 2026, limit = 20) =>
    apiClient.get<Match[]>(`/matches/upcoming?season=${season}&limit=${limit}`),

  getMatch: (matchId: number) => apiClient.get<Match>(`/matches/${matchId}`)
}

