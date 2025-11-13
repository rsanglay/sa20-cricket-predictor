import { apiClient } from '../client'
import { Team, TeamComparison, TeamDetail } from '../../types/team'

export const teamsAPI = {
  getAll: () => apiClient.get<Team[]>('/teams'),
  getTeam: (teamId: number) => apiClient.get<TeamDetail>(`/teams/${teamId}`),
  compareTeams: (teamIds: number[]) => apiClient.post<TeamComparison>('/teams/compare', teamIds)
}
