import React from 'react'
import { motion } from 'framer-motion'
import { Standing } from '../types'
import { Trophy } from 'lucide-react'

interface StandingsTableProps {
  standings: Standing[]
}

const StandingsTableComponent = ({ standings }: StandingsTableProps) => {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-md">
      <h3 className="text-lg font-bold text-slate-900 mb-4">League Standings</h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="text-left py-3 px-4 text-slate-600 font-semibold text-sm">Pos</th>
              <th className="text-left py-3 px-4 text-slate-600 font-semibold text-sm">Team</th>
              <th className="text-center py-3 px-4 text-slate-600 font-semibold text-sm">P</th>
              <th className="text-center py-3 px-4 text-slate-600 font-semibold text-sm">W</th>
              <th className="text-center py-3 px-4 text-slate-600 font-semibold text-sm">L</th>
              <th className="text-center py-3 px-4 text-slate-600 font-semibold text-sm">NR</th>
              <th className="text-center py-3 px-4 text-slate-600 font-semibold text-sm">Pts</th>
              <th className="text-center py-3 px-4 text-slate-600 font-semibold text-sm">NRR</th>
            </tr>
          </thead>
          <tbody>
            {standings.map((standing, index) => {
              const isTop4 = standing.position <= 4
              return (
                <motion.tr
                  key={standing.team_id}
                  layoutId={`team-${standing.team_id}`}
                  layout
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ 
                    delay: index * 0.02,
                    duration: 0.3,
                    ease: "easeOut",
                    layout: { 
                      type: "spring", 
                      stiffness: 300, 
                      damping: 30,
                      duration: 0.8
                    }
                  }}
                  style={{ willChange: 'transform' }}
                  className={`border-b border-slate-100 ${
                    isTop4 ? 'bg-emerald-50' : ''
                  }`}
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      {standing.position <= 4 && (
                        <Trophy className="w-4 h-4 text-emerald-600" />
                      )}
                      <span className={`font-bold ${
                        isTop4 ? 'text-emerald-600' : 'text-slate-900'
                      }`}>
                        {standing.position}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-slate-900 font-medium">{standing.team_name}</span>
                  </td>
                  <td className="py-3 px-4 text-center text-slate-600">
                    {standing.matches_played}
                  </td>
                  <td className="py-3 px-4 text-center text-emerald-600 font-semibold">
                    {standing.wins}
                  </td>
                  <td className="py-3 px-4 text-center text-red-600 font-semibold">
                    {standing.losses}
                  </td>
                  <td className="py-3 px-4 text-center text-amber-600 font-semibold">
                    {standing.no_result || 0}
                  </td>
                  <td className="py-3 px-4 text-center text-slate-900 font-bold">
                    {standing.points}
                  </td>
                  <td className="py-3 px-4 text-center text-slate-600">
                    {standing.net_run_rate.toFixed(2)}
                  </td>
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Memoize with custom comparison to prevent unnecessary re-renders
// Only re-render if standings data actually changed (by team ID, points, position)
export const StandingsTable = React.memo(StandingsTableComponent, (prevProps, nextProps) => {
  // If length changed, definitely re-render
  if (prevProps.standings.length !== nextProps.standings.length) {
    return false
  }
  
  // Compare each team's key properties
  return prevProps.standings.every((team, i) => {
    const nextTeam = nextProps.standings[i]
    return (
      team.team_id === nextTeam.team_id &&
      team.points === nextTeam.points &&
      team.position === nextTeam.position &&
      team.net_run_rate === nextTeam.net_run_rate &&
      team.wins === nextTeam.wins &&
      team.losses === nextTeam.losses
    )
  })
})

