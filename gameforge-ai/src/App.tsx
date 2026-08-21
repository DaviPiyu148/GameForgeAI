import { Routes, Route, useLocation, Navigate } from 'react-router-dom';
import HomePage from './pages/HomePage';
import NoMatchesPage from './pages/NoMatchesPage';
import BuilderPage from './pages/BuilderPage';
import SuccessStatusPage from './pages/SuccessStatusPage';
import ErrorStatusPage from './pages/ErrorStatusPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import { PageContainer } from './components/Shared/PageContainer';
import { AuthModal } from './components/Shared/AuthModal';

function App() {
  const location = useLocation();
  const isBuilderRoute = location.pathname === '/build';

  // Builder has its own full-screen IDE layout, skip PageContainer
  if (isBuilderRoute) {
    return (
      <div key={location.pathname} className="page-enter h-screen flex flex-col">
        <Routes>
          <Route path="/build" element={<BuilderPage />} />
          <Route path="*" element={<Navigate to="/build" replace />} />
        </Routes>
        <AuthModal />
      </div>
    );
  }

  return (
    <PageContainer>
      <div key={location.pathname} className="page-enter flex-1 flex flex-col">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/discover/no-matches" element={<NoMatchesPage />} />
          <Route path="/status/success" element={<SuccessStatusPage />} />
          <Route path="/status/error" element={<ErrorStatusPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <AuthModal />
      </div>
    </PageContainer>
  );
}

export default App;
