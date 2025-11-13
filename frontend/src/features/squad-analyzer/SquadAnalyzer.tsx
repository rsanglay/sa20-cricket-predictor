import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Loading from '../../components/common/Loading'
import { analyticsAPI } from '../../api/endpoints/analytics'
import { TeamSeasonStat } from '../../types/analytics'

const SquadAnalyzer = () => {
  const [competition] = useState('sa20')
  const { data: stats, isLoading } = useQuery({
    queryKey: ['analytics-team-stats', competition],
    queryFn: () => analyticsAPI.getTeamStats({ competition })
  })

  const seasons = useMemo(() => {
    const unique = new Set<string>()
    stats?.forEach((row) => unique.add(String(row.season)))
    return Array.from(unique).sort().reverse()
  }, [stats])

  const [selectedSeason, setSelectedSeason] = useState<string | undefined>(undefined)

  const filtered: TeamSeasonStat[] = useMemo(() => {
    if (!stats || stats.length === 0) return []
    const seasonToUse = selectedSeason ?? (seasons.length > 0 ? seasons[0] : undefined)
    return stats
      .filter((row) => (seasonToUse ? String(row.season) === seasonToUse : true))
      .sort((a, b) => b.win_percentage - a.win_percentage)
  }, [stats, selectedSeason, seasons])

  if (isLoading) return <Loading message="Loading squad analytics..." />

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wider font-semibold text-emerald-600">Squad intelligence</p>
        <h1 className="text-3xl font-bold text-slate-900">Squad Analyzer</h1>
        <p className="max-w-2xl text-sm text-slate-600">
          Compare franchise performance across seasons using win percentages and run rates.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Competition Overview</h2>
            <p className="text-sm text-slate-600">Historical record for {competition.toUpperCase()} franchises.</p>
          </div>
          {seasons.length > 0 && (
            <select
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-200 md:w-48"
              value={selectedSeason ?? seasons[0]}
              onChange={(event) => setSelectedSeason(event.target.value)}
            >
              {seasons.map((season) => (
                <option key={season} value={season}>
                  Season {season}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="mt-6 overflow-x-auto">
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
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
                  Avg Runs
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 bg-white">
              {filtered.map((row) => (
                <tr key={`${row.team_name}-${row.season}`} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-900">{row.team_name}</td>
                  <td className="px-4 py-3 text-right text-sm text-slate-700">{row.matches_played}</td>
                  <td className="px-4 py-3 text-right text-sm text-slate-700">{row.wins}</td>
                  <td className="px-4 py-3 text-right text-sm font-semibold text-slate-900">
                    {(row.win_percentage * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right text-sm font-semibold text-slate-900">{row.run_rate.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right text-sm text-slate-700">
                    {(row.total_runs / Math.max(row.matches_played, 1)).toFixed(1)}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-sm text-slate-500">
                    No data available. Run the ingestion and aggregation pipeline to populate analytics tables.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default SquadAnalyzer
