import { apiClient } from '../client'
import { Player, PlayerDetail, PlayerStats, PlayerProjection } from '../../types/player'

export const playersAPI = {
  getAll: (params?: { teamId?: number; role?: string; country?: string; onlyWithProjection?: boolean; onlyWithImages?: boolean }) => {
    const search = new URLSearchParams()
    if (params?.teamId) search.append('team_id', String(params.teamId))
    if (params?.role) search.append('role', params.role)
    if (params?.country) search.append('country', params.country)
    if (params?.onlyWithProjection) search.append('only_with_projection', 'true')
    if (params?.onlyWithImages) search.append('only_with_images', 'true')
    const query = search.toString()
    return apiClient.get<Player[]>(`/players${query ? `?${query}` : ''}`)
  },
  getPlayer: (playerId: number) => apiClient.get<PlayerDetail>(`/players/${playerId}`),
  getStats: (playerId: number, season?: number) =>
    apiClient.get<PlayerStats>(`/players/${playerId}/stats${season ? `?season=${season}` : ''}`),
  getProjection: (playerId: number) => apiClient.get<PlayerProjection>(`/players/${playerId}/projection`)
}
