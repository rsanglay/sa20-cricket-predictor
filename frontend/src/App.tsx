import { Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import Loading from './components/common/Loading'
import {
  LazyHome,
  LazyPlayerProfiler,
  LazyMatchPredictor,
  LazyFantasyOptimizer,
  LazyTeams,
  LazySeasonSimulatorV2
} from './utils/lazyLoad'

function App() {
  return (
    <MainLayout>
      <Suspense fallback={<Loading />}> 
        <Routes>
          <Route path="/" element={<LazyHome />} />
          <Route path="/season-simulator-v2" element={<LazySeasonSimulatorV2 />} />
          <Route path="/teams" element={<LazyTeams />} />
          <Route path="/players" element={<LazyPlayerProfiler />} />
          <Route path="/players/:id" element={<LazyPlayerProfiler />} />
          <Route path="/matches" element={<LazyMatchPredictor />} />
          <Route path="/fantasy" element={<LazyFantasyOptimizer />} />
        </Routes>
      </Suspense>
    </MainLayout>
  )
}

export default App
