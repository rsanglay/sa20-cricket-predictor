import { useMemo, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import Loading from '../../components/common/Loading'
import { predictionsAPI } from '../../api/endpoints/predictions'
import { teamsAPI } from '../../api/endpoints/teams'
import { playersAPI } from '../../api/endpoints/players'
import StandingsTable from './StandingsTable'
import { analyticsAPI } from '../../api/endpoints/analytics'
import { TeamSeasonStat } from '../../types/analytics'
import { Trophy, TrendingUp, Users, Award, AlertTriangle, Crown } from 'lucide-react'
import { Team } from '../../types/team'
import { Player } from '../../types/player'

const SeasonPredictor = () => {
  const [numSimulations, setNumSimulations] = useState(1000)
  const [customXIs, setCustomXIs] = useState<Record<number, number[]>>({})
  const [selectedTeam, setSelectedTeam] = useState<number | null>(null)

  const { data: teams } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsAPI.getAll()
  })

  const { data: players } = useQuery({
    queryKey: ['players', selectedTeam],
    queryFn: () => playersAPI.getAll(selectedTeam ? { teamId: selectedTeam } : undefined),
    enabled: selectedTeam !== null
  })

  const simulationMutation = useMutation({
    mutationFn: () => predictionsAPI.simulateSeason(numSimulations, Object.keys(customXIs).length > 0 ? customXIs : undefined)
  })

  const { data: baselineStats } = useQuery({
    queryKey: ['analytics-team-stats', 'sa20'],
    queryFn: () => analyticsAPI.getTeamStats({ competition: 'sa20' })
  })

  const teamMap = useMemo(() => {
    if (!teams) return new Map()
    return new Map(teams.map(t => [t.id, t.name]))
  }, [teams])

  const latestSeasonStats = useMemo(() => {
    if (!baselineStats || baselineStats.length === 0) return [] as TeamSeasonStat[]
    const latestSeason = baselineStats.reduce<string | number>((acc, curr) => {
      if (!acc) return curr.season
      return String(curr.season) > String(acc) ? curr.season : acc
    }, '')
    return baselineStats
      .filter((row) => String(row.season) === String(latestSeason))
      .sort((a, b) => b.win_percentage - a.win_percentage)
  }, [baselineStats])

  const handleSimulate = async () => {
    simulationMutation.mutate()
  }

  const handleSelectTeam = (teamId: number) => {
    setSelectedTeam(teamId)
  }

  const handleTogglePlayer = (playerId: number) => {
    if (!selectedTeam) return
    const currentXI = customXIs[selectedTeam] || []
    const isSelected = currentXI.includes(playerId)
    
    if (isSelected) {
      setCustomXIs({
        ...customXIs,
        [selectedTeam]: currentXI.filter(id => id !== playerId)
      })
    } else {
      if (currentXI.length < 11) {
        setCustomXIs({
          ...customXIs,
          [selectedTeam]: [...currentXI, playerId]
        })
      }
    }
  }

  const seasonPrediction = simulationMutation.data
  const isFetching = simulationMutation.isPending

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wider font-semibold text-emerald-600">Season outlook</p>
        <h1 className="text-3xl font-bold text-slate-900">SA20 Season Predictor</h1>
        <p className="max-w-2xl text-sm text-slate-600">
          Simulate the complete SA20 2026 tournament with custom team XIs. Monte Carlo modelling predicts standings, 
          playoff probabilities, championship odds, and individual player awards.
        </p>
      </div>

      {/* Custom XI Selection */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
        <div className="flex items-center gap-2 mb-4">
          <Users className="h-5 w-5 text-emerald-600" />
          <h2 className="text-xl font-bold text-slate-900">Custom XI Selection (Optional)</h2>
        </div>
        <p className="text-sm text-slate-600 mb-4">
          Select custom playing XIs for each team. If not specified, all available players will be used.
        </p>
        
        {teams && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {teams.map((team) => {
              const teamXI = customXIs[team.id] || []
              return (
                <div
                  key={team.id}
                  className={`rounded-lg border p-4 cursor-pointer transition ${
                    selectedTeam === team.id
                      ? 'border-emerald-500 bg-emerald-50'
                      : 'border-slate-200 hover:border-emerald-300'
                  }`}
                  onClick={() => handleSelectTeam(team.id)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-semibold text-slate-900">{team.name}</div>
                    <span className="text-xs text-slate-600">{teamXI.length}/11 selected</span>
                  </div>
                  {teamXI.length > 0 && (
                    <div className="text-xs text-emerald-700 mt-2">
                      {teamXI.length} players selected
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {selectedTeam && players && (
          <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="font-semibold text-slate-900 mb-3">
              Select XI for {teamMap.get(selectedTeam)}
            </h3>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3 max-h-96 overflow-y-auto">
              {players.map((player) => {
                const isSelected = customXIs[selectedTeam]?.includes(player.id) || false
                return (
                  <button
                    key={player.id}
                    onClick={() => handleTogglePlayer(player.id)}
                    className={`text-left rounded-lg border p-3 transition ${
                      isSelected
                        ? 'border-emerald-500 bg-emerald-100'
                        : 'border-slate-200 hover:border-emerald-300'
                    }`}
                  >
                    <div className="font-semibold text-sm text-slate-900">{player.name}</div>
                    <div className="text-xs text-slate-600 mt-1">
                      {player.role?.replace('_', ' ')} • {player.country}
                    </div>
                  </button>
                )
              })}
            </div>
            <div className="mt-4 text-sm text-slate-600">
              Selected: {customXIs[selectedTeam]?.length || 0}/11 players
            </div>
          </div>
        )}
      </div>

      {/* Simulation Controls */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
        <label className="block text-sm font-semibold text-slate-700">
          Number of simulations
        </label>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-center">
          <input
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-slate-900 transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 md:w-48"
            type="number"
            min={500}
            max={50000}
            step={500}
            value={numSimulations}
            onChange={(event) => setNumSimulations(Number(event.target.value))}
          />
          <button
            className="w-full rounded-lg border-2 border-emerald-600 bg-emerald-600 px-5 py-2 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-700 md:w-auto disabled:opacity-50"
            onClick={handleSimulate}
            disabled={isFetching}
          >
            {isFetching ? 'Running Simulation...' : 'Run Simulation'}
          </button>
        </div>
      </div>

      {isFetching && <Loading message="Running season simulation..." />}

      {seasonPrediction && !isFetching ? (
        <div className="space-y-6">
          {/* Standings */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="h-6 w-6 text-emerald-600" />
              <h2 className="text-2xl font-bold text-slate-900">Group Stage Standings</h2>
            </div>
            <p className="text-sm text-slate-600 mb-4">
              Based on {seasonPrediction.num_simulations.toLocaleString()} Monte Carlo simulations of all group stage matches.
            </p>
            <StandingsTable standings={seasonPrediction.predicted_standings} teamMap={teamMap} />
          </div>

          {/* Awards Section */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {/* Orange Cap */}
            {seasonPrediction.orange_cap && (
              <div className="rounded-xl border-2 border-orange-300 bg-gradient-to-br from-orange-50 to-orange-100/50 p-6 shadow-md">
                <div className="flex items-center gap-2 mb-3">
                  <Award className="h-5 w-5 text-orange-600" />
                  <h3 className="text-lg font-bold text-slate-900">Orange Cap</h3>
                </div>
                <div className="space-y-2">
                  <div className="text-xl font-bold text-slate-900">{seasonPrediction.orange_cap.player_name}</div>
                  <div className="text-sm text-slate-600">{seasonPrediction.orange_cap.team_name}</div>
                  <div className="text-2xl font-bold text-orange-700">
                    {seasonPrediction.orange_cap.avg_runs.toFixed(1)} runs
                  </div>
                  <div className="text-xs text-slate-500">
                    Range: {seasonPrediction.orange_cap.total_runs_range[0].toFixed(0)} - {seasonPrediction.orange_cap.total_runs_range[1].toFixed(0)}
                  </div>
                </div>
              </div>
            )}

            {/* Purple Cap */}
            {seasonPrediction.purple_cap && (
              <div className="rounded-xl border-2 border-purple-300 bg-gradient-to-br from-purple-50 to-purple-100/50 p-6 shadow-md">
                <div className="flex items-center gap-2 mb-3">
                  <Award className="h-5 w-5 text-purple-600" />
                  <h3 className="text-lg font-bold text-slate-900">Purple Cap</h3>
                </div>
                <div className="space-y-2">
                  <div className="text-xl font-bold text-slate-900">{seasonPrediction.purple_cap.player_name}</div>
                  <div className="text-sm text-slate-600">{seasonPrediction.purple_cap.team_name}</div>
                  <div className="text-2xl font-bold text-purple-700">
                    {seasonPrediction.purple_cap.avg_wickets.toFixed(1)} wickets
                  </div>
                  <div className="text-xs text-slate-500">
                    Range: {seasonPrediction.purple_cap.total_wickets_range[0].toFixed(0)} - {seasonPrediction.purple_cap.total_wickets_range[1].toFixed(0)}
                  </div>
                </div>
              </div>
            )}

            {/* MVP */}
            {seasonPrediction.mvp && (
              <div className="rounded-xl border-2 border-amber-300 bg-gradient-to-br from-amber-50 to-amber-100/50 p-6 shadow-md">
                <div className="flex items-center gap-2 mb-3">
                  <Crown className="h-5 w-5 text-amber-600" />
                  <h3 className="text-lg font-bold text-slate-900">MVP</h3>
                </div>
                <div className="space-y-2">
                  <div className="text-xl font-bold text-slate-900">{seasonPrediction.mvp.player_name}</div>
                  <div className="text-sm text-slate-600">{seasonPrediction.mvp.team_name}</div>
                  <div className="text-sm text-slate-700">
                    {seasonPrediction.mvp.avg_runs.toFixed(1)} runs • {seasonPrediction.mvp.avg_wickets.toFixed(1)} wickets
                  </div>
                  <div className="text-xs text-slate-500">
                    MVP Score: {seasonPrediction.mvp.mvp_score.toFixed(1)}
                  </div>
                </div>
              </div>
            )}

            {/* Champion */}
            {seasonPrediction.champion && (
              <div className="rounded-xl border-2 border-amber-300 bg-gradient-to-br from-amber-50 to-amber-100/50 p-6 shadow-md">
                <div className="flex items-center gap-2 mb-3">
                  <Trophy className="h-5 w-5 text-amber-600" />
                  <h3 className="text-lg font-bold text-slate-900">Predicted Champion</h3>
                </div>
                <div className="space-y-2">
                  <div className="text-xl font-bold text-slate-900">{seasonPrediction.champion.team_name}</div>
                  <div className="text-2xl font-bold text-amber-700">
                    {seasonPrediction.champion.win_probability.toFixed(1)}%
                  </div>
                  <div className="text-xs text-slate-500">championship probability</div>
                </div>
              </div>
            )}
          </div>

          {/* Team of the Tournament */}
          {seasonPrediction.team_of_tournament && seasonPrediction.team_of_tournament.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
              <h2 className="text-xl font-bold text-slate-900 mb-4">Team of the Tournament</h2>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {seasonPrediction.team_of_tournament.map((player, idx) => (
                  <div key={player.player_id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <div className="font-semibold text-slate-900">{player.player_name}</div>
                        <div className="text-xs text-slate-600">{player.team_name} • {player.role.replace('_', ' ')}</div>
                      </div>
                      <span className="text-xs font-semibold text-emerald-700">#{idx + 1}</span>
                    </div>
                    <div className="text-xs text-slate-700 mt-2">
                      {player.avg_runs.toFixed(1)} runs • {player.avg_wickets.toFixed(1)} wickets
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upset Tracker */}
          {seasonPrediction.upset_tracker && seasonPrediction.upset_tracker.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="h-5 w-5 text-blue-600" />
                <h2 className="text-xl font-bold text-slate-900">Upset Tracker</h2>
              </div>
              <p className="text-sm text-slate-600 mb-4">
                Teams that exceeded expectations in the simulation.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                {seasonPrediction.upset_tracker.map((upset) => (
                  <div key={upset.team_id} className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                    <div className="font-semibold text-slate-900 mb-2">{upset.team_name}</div>
                    <div className="text-sm text-slate-700">
                      Expected: {upset.expected_position.toFixed(1)} • Actual: {upset.actual_avg_position.toFixed(1)}
                    </div>
                    <div className="text-xs text-blue-700 mt-1">
                      Improved by {upset.improvement.toFixed(1)} positions
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Playoff Probabilities */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
            <h2 className="text-xl font-bold text-slate-900 mb-4">Playoff Probabilities</h2>
            <p className="text-sm text-slate-600 mb-4">
              Probability of each team finishing in the top 4 and advancing to playoffs.
            </p>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {seasonPrediction.predicted_standings.map((standing) => (
                <div
                  key={standing.team_id}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-4"
                >
                  <div className="text-sm font-semibold text-slate-900 mb-2">
                    {teamMap.get(standing.team_id) || `Team ${standing.team_id}`}
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-bold text-emerald-700">
                      {standing.playoff_probability.toFixed(1)}%
                    </span>
                    <span className="text-xs text-slate-500">playoff chance</span>
                  </div>
                  <div className="mt-2 h-2 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-600 transition-all"
                      style={{ width: `${Math.min(standing.playoff_probability, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Championship Probabilities */}
          <div className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50 to-amber-100/50 p-6 shadow-md">
            <div className="flex items-center gap-3 mb-4">
              <Trophy className="h-6 w-6 text-amber-600" />
              <h2 className="text-xl font-bold text-slate-900">Championship Probabilities</h2>
            </div>
            <p className="text-sm text-slate-600 mb-4">
              Probability of winning the SA20 2026 championship after playoffs and final.
            </p>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {seasonPrediction.predicted_standings
                .sort((a, b) => b.championship_probability - a.championship_probability)
                .map((standing) => (
                  <div
                    key={standing.team_id}
                    className="rounded-lg border border-amber-200 bg-white p-4"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm font-semibold text-slate-900">
                        {teamMap.get(standing.team_id) || `Team ${standing.team_id}`}
                      </div>
                      <span className="text-xs font-semibold text-amber-700">
                        {standing.championship_probability.toFixed(1)}%
                      </span>
                    </div>
                    <div className="h-2 bg-amber-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-amber-600 transition-all"
                        style={{ width: `${Math.min(standing.championship_probability, 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      ) : (
        !isFetching && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-slate-600 shadow-md">
            Run the simulation to generate season projections.
          </div>
        )
      )}

      {latestSeasonStats.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Most Recent SA20 Season Snapshot</h2>
              <p className="text-sm text-slate-600">Historical form helps contextualise simulation results.</p>
            </div>
            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs uppercase tracking-wider font-semibold text-emerald-700">
              Season {latestSeasonStats[0]?.season}
            </span>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-600">Team</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Matches
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Wins
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Win %
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Run Rate
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {latestSeasonStats.map((row) => (
                  <tr key={`${row.team_name}-${row.season}`} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-sm font-semibold text-slate-900">{row.team_name}</td>
                    <td className="px-4 py-3 text-right text-sm text-slate-700">{row.matches_played}</td>
                    <td className="px-4 py-3 text-right text-sm text-slate-700">{row.wins}</td>
                    <td className="px-4 py-3 text-right text-sm font-semibold text-slate-900">
                      {(row.win_percentage * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-sm font-semibold text-slate-900">{row.run_rate.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export default SeasonPredictor
