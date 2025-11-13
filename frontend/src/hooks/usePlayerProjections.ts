import { useQuery } from '@tanstack/react-query'
import { playersAPI } from '../api/endpoints/players'
import { Player, PlayerProjection } from '../types/player'

export interface PlayerProjectionWithMeta extends PlayerProjection {
  role: Player['role']
  country: string
  team_id?: number
}

const usePlayerProjections = () =>
  useQuery<PlayerProjectionWithMeta[]>({
    queryKey: ['player-projections-all'],
    queryFn: async () => {
      try {
        const players = await playersAPI.getAll({ onlyWithProjection: true })
        const projections = await Promise.allSettled(
          players
            .filter(player => player.has_projection !== false)
            .map(async (player) => {
            try {
              const projection = await playersAPI.getProjection(player.id)
              return {
                ...projection,
                role: player.role,
                country: player.country,
                team_id: player.team_id
              } as PlayerProjectionWithMeta
            } catch (error: any) {
              // Skip 503 (service unavailable) and 404 (player not found) errors
              if (error?.response?.status === 503 || error?.response?.status === 404) {
                return null
              }
              throw error
            }
          })
        )
        return projections
          .filter((result): result is PromiseFulfilledResult<PlayerProjectionWithMeta | null> => 
            result.status === 'fulfilled' && result.value !== null
          )
          .map(result => result.value as PlayerProjectionWithMeta)
      } catch (error) {
        // If the service is unavailable, return empty array instead of failing
        console.warn('Player projections unavailable:', error)
        return []
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false, // Don't retry if models aren't available
  })

export default usePlayerProjections
