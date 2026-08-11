import { Routes, Route, useLocation } from 'react-router-dom'
import HomePage from './pages/HomePage'
import NoMatchesPage from './pages/NoMatchesPage'
import BuilderPage from './pages/BuilderPage'
import SuccessStatusPage from './pages/SuccessStatusPage'
import ErrorStatusPage from './pages/ErrorStatusPage'
import DashboardPage from './pages/DashboardPage'
import ProfilePage from './pages/ProfilePage'
import { PageContainer } from './components/Shared/PageContainer'

function App() {
  const location = useLocation();
  const isBuilderRoute = location.pathname === '/build';

  // Builder has its own full-screen IDE layout, skip PageContainer
  if (isBuilderRoute) {
    return (
      <Routes>
        <Route path="/build" element={<BuilderPage />} />
      </Routes>
    );
  }

  return (
    <PageContainer>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/discover/no-matches" element={<NoMatchesPage />} />
        <Route path="/status/success" element={<SuccessStatusPage />} />
        <Route path="/status/error" element={<ErrorStatusPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Routes>
    </PageContainer>
  )
}

export default App
