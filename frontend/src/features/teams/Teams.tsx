import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { teamsAPI } from '../../api/endpoints/teams'
import { playersAPI } from '../../api/endpoints/players'
import Loading from '../../components/common/Loading'
import { Team } from '../../types/team'
import { Player } from '../../types/player'
import { Users, Trophy } from 'lucide-react'

const Teams = () => {
  const navigate = useNavigate()
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null)

  const { data: teams, isLoading: teamsLoading } = useQuery({
    queryKey: ['teams'],
    queryFn: () => teamsAPI.getAll()
  })

  const { data: players, isLoading: playersLoading } = useQuery({
    queryKey: ['players-by-team', selectedTeamId],
    queryFn: () => playersAPI.getAll({ teamId: selectedTeamId! }),
    enabled: selectedTeamId !== null,
    // Backend automatically filters by images when teamId is provided
  })

  const selectedTeam = teams?.find(t => t.id === selectedTeamId)

  if (teamsLoading) return <Loading message="Loading teams..." />

  return (
    <div className="space-y-10">
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 p-3 shadow-lg">
            <Users className="h-6 w-6 text-white" />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-bold text-emerald-600">Squad Directory</p>
            <h1 className="text-4xl font-extrabold text-slate-900 mt-1">SA20 Teams & Players</h1>
          </div>
        </div>
        <p className="max-w-3xl text-base text-slate-600 leading-relaxed">
          Browse all SA20 teams and explore comprehensive player profiles with photos, roles, statistics, and performance data. Click on any team to view their full squad.
        </p>
      </div>

      {/* Teams Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {teams?.map((team) => (
          <button
            key={team.id}
            onClick={() => setSelectedTeamId(team.id === selectedTeamId ? null : team.id)}
            className={`rounded-2xl border-2 p-6 text-left transition-all transform ${
              selectedTeamId === team.id
                ? 'border-emerald-500 bg-gradient-to-br from-emerald-50 to-emerald-100 shadow-xl scale-105 ring-4 ring-emerald-100'
                : 'border-slate-200 bg-white hover:border-emerald-300 hover:shadow-lg hover:-translate-y-1'
            }`}
          >
            <div className="flex items-center gap-4">
              <div className={`flex h-16 w-16 items-center justify-center rounded-xl text-2xl font-extrabold shadow-md transition-all ${
                selectedTeamId === team.id
                  ? 'bg-emerald-500 text-white scale-110'
                  : 'bg-gradient-to-br from-slate-100 to-slate-200 text-slate-700'
              }`}>
                {team.short_name}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-extrabold text-slate-900 truncate">{team.name}</h3>
                <p className="text-sm text-slate-600 mt-1 truncate">{team.home_venue || 'Venue TBD'}</p>
              </div>
              <Trophy className={`h-6 w-6 transition-transform ${selectedTeamId === team.id ? 'text-emerald-600 scale-110' : 'text-slate-400'}`} />
            </div>
          </button>
        ))}
      </div>

      {/* Players Grid for Selected Team */}
      {selectedTeamId && selectedTeam && (
        <div className="rounded-2xl border-2 border-emerald-200 bg-white p-8 shadow-xl">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-extrabold text-slate-900 mb-2">{selectedTeam.name} Squad</h2>
              <p className="text-base text-slate-600">Click on a player card to view their detailed profile and statistics</p>
            </div>
            <button
              onClick={() => setSelectedTeamId(null)}
              className="rounded-xl border-2 border-slate-300 bg-white px-5 py-2.5 text-sm font-bold text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-400 hover:shadow-md"
            >
              Close
            </button>
          </div>

          {playersLoading ? (
            <Loading message="Loading players..." />
          ) : players && players.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {players
                .filter((player) => {
                  // Double-check: only show players with valid images
                  if (!player.image_url) return false
                  const urlLower = player.image_url.toLowerCase()
                  const uiPatterns = ['instagram', 'logo', 'search', 'hamburger', 'chevron', 'icon', 'button', 'menu', 'arrow']
                  if (uiPatterns.some(pattern => urlLower.includes(pattern))) return false
                  // Image URL should contain image-related keywords or be a valid URL
                  return urlLower.includes('player') || 
                         urlLower.includes('squad') || 
                         urlLower.includes('team') || 
                         urlLower.includes('photo') || 
                         urlLower.includes('image') || 
                         urlLower.includes('.jpg') || 
                         urlLower.includes('.jpeg') || 
                         urlLower.includes('.png') || 
                         urlLower.includes('.webp') || 
                         urlLower.startsWith('http')
                })
                .map((player) => (
                  <PlayerCard 
                    key={player.id} 
                    player={player} 
                    onClick={() => navigate(`/players/${player.id}`)}
                  />
                ))}
            </div>
          ) : (
            <div className="py-12 text-center text-slate-500">
              <Users className="mx-auto h-12 w-12 text-slate-300" />
              <p className="mt-4">No players found for this team</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface PlayerCardProps {
  player: Player
  onClick?: () => void
}

const PlayerCard = ({ player, onClick }: PlayerCardProps) => {
  const roleColors: Record<string, string> = {
    batsman: 'bg-blue-100 text-blue-700',
    bowler: 'bg-red-100 text-red-700',
    all_rounder: 'bg-purple-100 text-purple-700',
    wicket_keeper: 'bg-amber-100 text-amber-700',
  }

  const roleLabels: Record<string, string> = {
    batsman: 'BATSMAN',
    bowler: 'BOWLER',
    all_rounder: 'ALL-ROUNDER',
    wicket_keeper: 'WK',
  }

  const getInitials = (name: string) => {
    const words = name.split(' ').filter(w => w.length > 0)
    if (words.length >= 2) {
      return (words[0][0] + words[words.length - 1][0]).toUpperCase()
    }
    return name.substring(0, 2).toUpperCase()
  }

  const isValidImageUrl = (url: string | null | undefined): boolean => {
    if (!url) return false
    const urlLower = url.toLowerCase()
    // Filter out UI element images
    const uiPatterns = ['instagram', 'logo', 'search', 'hamburger', 'chevron', 'icon', 'button', 'menu', 'arrow', 'placeholder', 'default']
    if (uiPatterns.some(pattern => urlLower.includes(pattern))) return false
    // Image URL should contain image-related keywords or be a valid URL
    return urlLower.includes('player') || 
           urlLower.includes('squad') || 
           urlLower.includes('team') || 
           urlLower.includes('photo') || 
           urlLower.includes('image') || 
           urlLower.includes('.jpg') || 
           urlLower.includes('.jpeg') || 
           urlLower.includes('.png') || 
           urlLower.includes('.webp') || 
           urlLower.startsWith('http')
  }

  const hasValidImage = isValidImageUrl(player.image_url)

  return (
    <button
      onClick={onClick}
      className="group relative overflow-hidden rounded-2xl border-2 border-slate-200 bg-white text-left transition-all hover:border-emerald-400 hover:shadow-2xl w-full transform hover:-translate-y-1"
    >
      <div className="relative h-64 bg-gradient-to-br from-emerald-50 via-slate-50 to-emerald-50 overflow-hidden flex items-center justify-center p-4">
        {hasValidImage ? (
          <img
            src={player.image_url!}
            alt={player.name}
            className="w-full h-full object-contain object-center transition-transform duration-500 group-hover:scale-110"
            style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            onError={(e) => {
              // Fallback to placeholder if image fails to load
              const target = e.target as HTMLImageElement
              target.style.display = 'none'
              const placeholder = target.parentElement?.querySelector('.placeholder')
              if (placeholder) {
                (placeholder as HTMLElement).style.display = 'flex'
              }
            }}
          />
        ) : null}
        <div
          className={`absolute inset-0 flex items-center justify-center ${hasValidImage ? 'hidden placeholder' : 'flex'}`}
        >
          <div className="flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 text-5xl font-bold text-white shadow-xl ring-4 ring-white/50">
            {getInitials(player.name)}
          </div>
        </div>
        <div className="absolute top-3 right-3">
          <span
            className={`rounded-full px-3 py-1.5 text-xs font-bold shadow-lg backdrop-blur-sm ${
              roleColors[player.role] || 'bg-slate-100 text-slate-700'
            }`}
          >
            {roleLabels[player.role] || player.role.toUpperCase()}
          </span>
        </div>
      </div>
      <div className="p-6 bg-white">
        <h3 className="font-extrabold text-lg text-slate-900 group-hover:text-emerald-700 transition-colors mb-2">
          {player.name}
        </h3>
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <span className="inline-flex items-center gap-1 font-semibold">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {player.country}
          </span>
          <span className="text-slate-300">•</span>
          <span className="font-medium">Age {player.age}</span>
        </div>
      </div>
    </button>
  )
}

export default Teams

