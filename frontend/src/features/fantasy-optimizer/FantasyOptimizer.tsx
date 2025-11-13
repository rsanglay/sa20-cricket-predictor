import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import Loading from '../../components/common/Loading'
import usePlayerProjections, { PlayerProjectionWithMeta } from '../../hooks/usePlayerProjections'
import { apiClient } from '../../api/client'
import { Zap, Users, DollarSign, TrendingUp, CheckCircle } from 'lucide-react'

interface OptimizedTeam {
  team: Array<{
    player_id: number
    player_name: string
    expected_points: number
    role: string
    team_id?: number
  }>
  captain?: {
    player_id: number
    player_name: string
    expected_points: number
  }
  vice_captain?: {
    player_id: number
    player_name: string
    expected_points: number
  }
  total_points: number
  total_cost: number
  budget_used: number
  budget_remaining: number
  role_counts: {
    batsman: number
    bowler: number
    all_rounder: number
    wicket_keeper: number
  }
  team_counts: Record<number, number>
  optimization_method?: string
}

const FantasyOptimizer = () => {
  const { data: projections, isLoading } = usePlayerProjections()
  const [budget, setBudget] = useState(100)
  const [maxPerTeam, setMaxPerTeam] = useState(7)
  const [minBatsmen, setMinBatsmen] = useState(3)
  const [minBowlers, setMinBowlers] = useState(3)
  const [minAllRounders, setMinAllRounders] = useState(1)
  const [minWicketKeepers, setMinWicketKeepers] = useState(1)

  const optimizeMutation = useMutation({
    mutationFn: async () => {
      // Call the fantasy optimization API
      const matchday = new Date().toISOString().split('T')[0] // Use today's date as matchday
      return apiClient.post<OptimizedTeam>('/fantasy/optimize', {
        matchday,
        budget,
        max_per_team: maxPerTeam,
        min_batsmen: minBatsmen,
        min_bowlers: minBowlers,
        min_all_rounders: minAllRounders,
        min_wicket_keepers: minWicketKeepers,
      })
    }
  })

  const topBatters = useMemo<PlayerProjectionWithMeta[]>(() => {
    if (!projections) return []
    return projections
      .filter((player) => player.role === 'batsman' || player.role === 'all_rounder')
      .sort((a, b) => b.predicted_runs - a.predicted_runs)
      .slice(0, 5)
  }, [projections])

  const topBowlers = useMemo<PlayerProjectionWithMeta[]>(() => {
    if (!projections) return []
    return projections
      .filter((player) => player.role === 'bowler' || player.role === 'all_rounder')
      .sort((a, b) => b.predicted_wickets - a.predicted_wickets)
      .slice(0, 5)
  }, [projections])

  const handleOptimize = () => {
    optimizeMutation.mutate()
  }

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-emerald-50 to-emerald-100/50 p-6 shadow-lg">
        <p className="text-xs uppercase tracking-wider font-semibold text-emerald-700">Roster craftsmanship</p>
        <h1 className="mt-3 text-3xl font-bold text-slate-900">Fantasy Optimizer</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-700">
          Build optimal fantasy teams using Integer Linear Programming (ILP) optimization. 
          Maximize expected points while respecting budget and team constraints.
        </p>
      </div>

      {/* Optimization Controls */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
        <h2 className="text-xl font-bold text-slate-900 mb-4">Optimization Parameters</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Budget (Credits)</label>
            <input
              type="number"
              min={50}
              max={200}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Max Players per Team</label>
            <input
              type="number"
              min={1}
              max={11}
              value={maxPerTeam}
              onChange={(e) => setMaxPerTeam(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Min Batsmen</label>
            <input
              type="number"
              min={1}
              max={6}
              value={minBatsmen}
              onChange={(e) => setMinBatsmen(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Min Bowlers</label>
            <input
              type="number"
              min={1}
              max={6}
              value={minBowlers}
              onChange={(e) => setMinBowlers(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Min All-Rounders</label>
            <input
              type="number"
              min={0}
              max={4}
              value={minAllRounders}
              onChange={(e) => setMinAllRounders(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Min Wicket Keepers</label>
            <input
              type="number"
              min={1}
              max={2}
              value={minWicketKeepers}
              onChange={(e) => setMinWicketKeepers(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
        </div>
        <button
          onClick={handleOptimize}
          disabled={optimizeMutation.isPending || isLoading}
          className="mt-6 w-full rounded-lg border-2 border-emerald-600 bg-emerald-600 px-5 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-700 disabled:opacity-50"
        >
          {optimizeMutation.isPending ? 'Optimizing...' : 'Generate Optimal Team'}
        </button>
      </div>

      {isLoading && <Loading message="Loading player projections..." />}

      {optimizeMutation.isPending && <Loading message="Running ILP optimization..." />}

      {optimizeMutation.data && !optimizeMutation.isPending && (
        <div className="space-y-6">
          {/* Optimization Results Summary */}
          <div className="rounded-xl border-2 border-emerald-300 bg-gradient-to-br from-emerald-50 to-emerald-100/50 p-6 shadow-md">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="h-5 w-5 text-emerald-600" />
              <h2 className="text-xl font-bold text-slate-900">Optimization Results</h2>
              {optimizeMutation.data.optimization_method && (
                <span className="ml-auto rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs uppercase tracking-wider font-semibold text-emerald-700">
                  {optimizeMutation.data.optimization_method}
                </span>
              )}
            </div>
            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-lg border border-emerald-200 bg-white p-4">
                <div className="text-xs font-semibold text-slate-600 mb-1">Total Points</div>
                <div className="text-2xl font-bold text-emerald-700">
                  {optimizeMutation.data.total_points.toFixed(1)}
                </div>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-white p-4">
                <div className="text-xs font-semibold text-slate-600 mb-1">Budget Used</div>
                <div className="text-2xl font-bold text-slate-900">
                  {optimizeMutation.data.budget_used.toFixed(1)}
                </div>
                <div className="text-xs text-slate-500">
                  of {budget} credits
                </div>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-white p-4">
                <div className="text-xs font-semibold text-slate-600 mb-1">Remaining</div>
                <div className="text-2xl font-bold text-slate-900">
                  {optimizeMutation.data.budget_remaining.toFixed(1)}
                </div>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-white p-4">
                <div className="text-xs font-semibold text-slate-600 mb-1">Players Selected</div>
                <div className="text-2xl font-bold text-slate-900">
                  {optimizeMutation.data.team.length}/11
                </div>
              </div>
            </div>
          </div>

          {/* Role Distribution */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Role Distribution</h3>
            <div className="grid gap-3 md:grid-cols-4">
              {Object.entries(optimizeMutation.data.role_counts).map(([role, count]) => (
                <div key={role} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm font-semibold text-slate-900 capitalize">
                    {role.replace('_', ' ')}
                  </div>
                  <div className="text-2xl font-bold text-emerald-700 mt-1">{count}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Optimized Team */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Optimized Team</h3>
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {optimizeMutation.data.team.map((player, idx) => {
                const isCaptain = optimizeMutation.data.captain?.player_id === player.player_id
                const isViceCaptain = optimizeMutation.data.vice_captain?.player_id === player.player_id
                return (
                  <div
                    key={player.player_id}
                    className={`rounded-lg border p-4 ${
                      isCaptain
                        ? 'border-amber-300 bg-amber-50'
                        : isViceCaptain
                        ? 'border-blue-300 bg-blue-50'
                        : 'border-slate-200 bg-slate-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-semibold text-slate-900">{player.player_name}</div>
                      {isCaptain && (
                        <span className="text-xs font-semibold text-amber-700">C</span>
                      )}
                      {isViceCaptain && (
                        <span className="text-xs font-semibold text-blue-700">VC</span>
                      )}
                    </div>
                    <div className="text-xs text-slate-600 mb-2">
                      {player.role.replace('_', ' ')} • Team {player.team_id}
                    </div>
                    <div className="text-sm font-semibold text-emerald-700">
                      {player.expected_points.toFixed(1)} pts
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {!isLoading && projections && (
        <div className="space-y-8">
          <div className="grid gap-6 md:grid-cols-3">
            <SummaryCard title="Projected squad value" value={`${budget.toFixed(1)} credits`} subtitle="Customise budget above." />
            <SummaryCard title="Batting core" value={`${topBatters[0]?.player_name ?? 'N/A'}`} subtitle="Highest projected runs." />
            <SummaryCard title="Strike bowling" value={`${topBowlers[0]?.player_name ?? 'N/A'}`} subtitle="Leading predicted wicket-taker." />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <ProjectionList title="Top Run Scorers" players={topBatters} metricKey="predicted_runs" metricLabel="Runs" />
            <ProjectionList title="Top Wicket Takers" players={topBowlers} metricKey="predicted_wickets" metricLabel="Wickets" />
          </div>
        </div>
      )}
    </div>
  )
}

const SummaryCard = ({ title, value, subtitle }: { title: string; value: string; subtitle: string }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
    <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</div>
    <div className="mt-3 text-2xl font-bold text-slate-900">{value}</div>
    <p className="mt-2 text-xs text-slate-600">{subtitle}</p>
  </div>
)

const ProjectionList = ({
  title,
  players,
  metricKey,
  metricLabel,
}: {
  title: string
  players: PlayerProjectionWithMeta[]
  metricKey: 'predicted_runs' | 'predicted_wickets'
  metricLabel: string
}) => (
  <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
    <h2 className="text-lg font-bold text-slate-900">{title}</h2>
    <ul className="mt-4 space-y-3">
      {players.map((player) => (
        <li
          key={player.player_id}
          className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
        >
          <div>
            <div className="font-semibold text-slate-900">{player.player_name}</div>
            <div className="text-xs text-slate-600">
              {player.role.replace('_', ' ')} • {player.country}
            </div>
          </div>
          <span className="text-sm font-semibold text-emerald-700">
            {metricLabel}: {(player[metricKey] as number).toFixed(1)}
          </span>
        </li>
      ))}
      {players.length === 0 && <li className="text-sm text-slate-500">No projections available.</li>}
    </ul>
  </div>
)

export default FantasyOptimizer
