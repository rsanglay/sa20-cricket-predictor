import { useState } from 'react'
import { Match, Standing } from '../types'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'
import { FileText, Image } from 'lucide-react'

interface AnalyticsDashboardProps {
  matches: Match[]
  standings: Standing[]
}

type Tab = 'standings' | 'fixtures' | 'statistics' | 'players' | 'teams'

export const AnalyticsDashboard = ({ matches, standings }: AnalyticsDashboardProps) => {
  const [activeTab, setActiveTab] = useState<Tab>('standings')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'standings', label: 'Standings' },
    { id: 'fixtures', label: 'Fixtures' },
    { id: 'statistics', label: 'Statistics' },
    { id: 'players', label: 'Players' },
    { id: 'teams', label: 'Teams' },
  ]

  // Prepare chart data
  const standingsChartData = standings.map(s => ({
    team: s.team_name,
    points: s.points,
    wins: s.wins,
    playoffProb: s.playoff_probability,
  }))

  const playoffProbData = standings.map(s => ({
    team: s.team_name,
    probability: s.playoff_probability,
  }))

  const exportToCSV = () => {
    // Simple CSV export
    const csv = [
      ['Team', 'Position', 'Points', 'Wins', 'Losses', 'Playoff Prob', 'Championship Prob'],
      ...standings.map(s => [
        s.team_name,
        s.position,
        s.points,
        s.wins,
        s.losses,
        s.playoff_probability,
        s.championship_probability,
      ]),
    ].map(row => row.join(',')).join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'sa20-standings.csv'
    a.click()
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] p-8 pb-32">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-4xl font-bold text-white">Analytics Dashboard</h1>
          <div className="flex gap-2">
            <button
              onClick={exportToCSV}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2 transition-colors"
            >
              <FileText className="w-4 h-4" />
              Export CSV
            </button>
            <button
              onClick={() => window.print()}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg flex items-center gap-2 transition-colors"
            >
              <Image className="w-4 h-4" />
              Export PNG
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-8 border-b border-slate-700">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 font-semibold transition-colors ${
                activeTab === tab.id
                  ? 'text-[#FF6B35] border-b-2 border-[#FF6B35]'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-6 border border-slate-700">
          {activeTab === 'standings' && (
            <div className="space-y-8">
              <div>
                <h3 className="text-2xl font-bold text-white mb-4">Final Standings</h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left py-3 px-4 text-slate-400 font-semibold">Pos</th>
                        <th className="text-left py-3 px-4 text-slate-400 font-semibold">Team</th>
                        <th className="text-center py-3 px-4 text-slate-400 font-semibold">P</th>
                        <th className="text-center py-3 px-4 text-slate-400 font-semibold">W</th>
                        <th className="text-center py-3 px-4 text-slate-400 font-semibold">L</th>
                        <th className="text-center py-3 px-4 text-slate-400 font-semibold">Pts</th>
                        <th className="text-center py-3 px-4 text-slate-400 font-semibold">Playoff %</th>
                        <th className="text-center py-3 px-4 text-slate-400 font-semibold">Champ %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {standings.map((standing) => (
                        <tr key={standing.team_id} className="border-b border-slate-700/50">
                          <td className="py-3 px-4 text-white font-bold">{standing.position}</td>
                          <td className="py-3 px-4 text-white">{standing.team_name}</td>
                          <td className="py-3 px-4 text-center text-slate-300">{standing.matches_played}</td>
                          <td className="py-3 px-4 text-center text-green-400">{standing.wins}</td>
                          <td className="py-3 px-4 text-center text-red-400">{standing.losses}</td>
                          <td className="py-3 px-4 text-center text-white font-bold">{standing.points}</td>
                          <td className="py-3 px-4 text-center text-slate-300">{standing.playoff_probability.toFixed(1)}%</td>
                          <td className="py-3 px-4 text-center text-slate-300">{standing.championship_probability.toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="text-2xl font-bold text-white mb-4">Points Distribution</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={standingsChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="team" stroke="#9CA3AF" />
                    <YAxis stroke="#9CA3AF" />
                    <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }} />
                    <Legend />
                    <Bar dataKey="points" fill="#FF6B35" />
                    <Bar dataKey="wins" fill="#00C48C" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {activeTab === 'fixtures' && (
            <div>
              <h3 className="text-2xl font-bold text-white mb-4">All Match Results</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {matches.map((match) => (
                  <div
                    key={match.id}
                    className="bg-slate-700/50 rounded-lg p-4 border border-slate-600"
                  >
                    <div className="text-sm text-slate-400 mb-2">Match {match.id}</div>
                    <div className="text-white font-semibold mb-1">{match.home_team_name}</div>
                    <div className="text-slate-500 text-xs mb-1">vs</div>
                    <div className="text-white font-semibold mb-2">{match.away_team_name}</div>
                    {match.completed && match.winner_name && (
                      <div className="text-sm text-[#FFD700]">Winner: {match.winner_name}</div>
                    )}
                    <div className="text-xs text-slate-500 mt-2">{match.venue_name}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'statistics' && (
            <div>
              <h3 className="text-2xl font-bold text-white mb-4">Playoff Probabilities</h3>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={playoffProbData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="team" stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" />
                  <Tooltip contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }} />
                  <Bar dataKey="probability" fill="#FFD700" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {activeTab === 'players' && (
            <div>
              <h3 className="text-2xl font-bold text-white mb-4">Player Statistics</h3>
              <div className="text-slate-400 text-center py-12">
                Player statistics coming soon...
              </div>
            </div>
          )}

          {activeTab === 'teams' && (
            <div>
              <h3 className="text-2xl font-bold text-white mb-4">Team Comparison</h3>
              <div className="text-slate-400 text-center py-12">
                Team comparison charts coming soon...
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

