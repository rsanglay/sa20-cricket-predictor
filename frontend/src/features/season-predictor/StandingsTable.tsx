import { Standing } from '../../types/prediction'

interface StandingsTableProps {
  standings: Standing[]
  teamMap?: Map<number, string>
}

const StandingsTable = ({ standings, teamMap }: StandingsTableProps) => {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
              Pos
            </th>
            <th className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
              Team
            </th>
            <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
              Avg Points
            </th>
            <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
              Playoff %
            </th>
            <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-slate-600">
              Championship %
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 bg-white">
          {standings.map((standing, index) => (
            <tr
              key={standing.team_id}
              className={index < 4 ? 'bg-emerald-50' : 'hover:bg-slate-50'}
            >
              <td className="px-4 py-3 font-bold text-slate-900">{index + 1}</td>
              <td className="px-4 py-3 font-semibold text-slate-900">
                {teamMap?.get(standing.team_id) || `Team ${standing.team_id}`}
              </td>
              <td className="px-4 py-3 text-right text-slate-700">{standing.avg_points.toFixed(1)}</td>
              <td className="px-4 py-3 text-right font-semibold text-emerald-700">{standing.playoff_probability.toFixed(1)}%</td>
              <td className="px-4 py-3 text-right font-semibold text-amber-700">{standing.championship_probability.toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default StandingsTable
