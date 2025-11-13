import { apiClient } from '../client'
import { MatchScorecard, PlayerSeasonStat, TeamSeasonStat } from '../../types/analytics'

export const analyticsAPI = {
  getTeamStats: async (params?: { competition?: string; season?: string | number }) => {
    const search = new URLSearchParams()
    if (params?.competition) search.append('competition', String(params.competition))
    if (params?.season) search.append('season', String(params.season))
    const query = search.toString()
    return apiClient.get<TeamSeasonStat[]>(`/analytics/team-stats${query ? `?${query}` : ''}`)
  },

  getPlayerStats: async (params?: {
    competition?: string
    season?: string | number
    teamName?: string
    minMatches?: number
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params?.competition) search.append('competition', String(params.competition))
    if (params?.season) search.append('season', String(params.season))
    if (params?.teamName) search.append('team_name', String(params.teamName))
    if (params?.minMatches !== undefined) search.append('min_matches', String(params.minMatches))
    if (params?.limit !== undefined) search.append('limit', String(params.limit))
    const query = search.toString()
    return apiClient.get<PlayerSeasonStat[]>(`/analytics/player-stats${query ? `?${query}` : ''}`)
  },

  getMatchScorecards: async (params?: {
    competition?: string
    season?: string | number
    teamName?: string
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params?.competition) search.append('competition', String(params.competition))
    if (params?.season) search.append('season', String(params.season))
    if (params?.teamName) search.append('team_name', String(params.teamName))
    if (params?.limit !== undefined) search.append('limit', String(params.limit))
    const query = search.toString()
    return apiClient.get<MatchScorecard[]>(`/analytics/match-scorecards${query ? `?${query}` : ''}`)
  },

  getSA20OfficialStats: async (params?: {
    statType?: 'batting' | 'bowling'
    season?: number
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params?.statType) search.append('stat_type', params.statType)
    if (params?.season) search.append('season', String(params.season))
    if (params?.limit) search.append('limit', String(params.limit))
    const query = search.toString()
    return apiClient.get<Record<string, any>[]>(`/analytics/sa20-official-stats${query ? `?${query}` : ''}`)
  },

  getBattingLeaderboard: async (params?: { season?: number; competition?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.season) search.append('season', String(params.season))
    if (params?.competition) search.append('competition', params.competition)
    if (params?.limit) search.append('limit', String(params.limit))
    const query = search.toString()
    return apiClient.get<Record<string, any>[]>(`/analytics/batting-leaderboard${query ? `?${query}` : ''}`)
  },

  getBowlingLeaderboard: async (params?: { season?: number; competition?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.season) search.append('season', String(params.season))
    if (params?.competition) search.append('competition', params.competition)
    if (params?.limit) search.append('limit', String(params.limit))
    const query = search.toString()
    return apiClient.get<Record<string, any>[]>(`/analytics/bowling-leaderboard${query ? `?${query}` : ''}`)
  },

  getHeadToHead: async (teamA: string, teamB: string, competition?: string) => {
    const search = new URLSearchParams()
    search.append('team_a', teamA)
    search.append('team_b', teamB)
    if (competition) search.append('competition', competition)
    return apiClient.get<Record<string, any>>(`/analytics/head-to-head?${search.toString()}`)
  }
}
