import { Routes, Route, useLocation, Navigate } from 'react-router-dom';
import HomePage from './pages/HomePage';
import NoMatchesPage from './pages/NoMatchesPage';
import BuilderPage from './pages/BuilderPage';
import SuccessStatusPage from './pages/SuccessStatusPage';
import ErrorStatusPage from './pages/ErrorStatusPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import DocumentationPage from './pages/DocumentationPage';
import ApiAccessPage from './pages/ApiAccessPage';
import CommunityPage from './pages/CommunityPage';
import SupportPage from './pages/SupportPage';
import PrivacyPage from './pages/PrivacyPage';
import PlaytestPage from './pages/PlaytestPage';
import { PageContainer } from './components/Shared/PageContainer';
import { AuthModal } from './components/Shared/AuthModal';
import { ToastContainer } from './components/Shared/ToastContainer';

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
        <ToastContainer />
      </div>
    );
  }

  const isPlaytestHarnessEnabled =
    Boolean(import.meta.env.DEV || import.meta.env.VITE_ENABLE_PLAYTEST_HARNESS === 'true');

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
          <Route path="/documentation" element={<DocumentationPage />} />
          <Route path="/api-access" element={<ApiAccessPage />} />
          <Route path="/community" element={<CommunityPage />} />
          <Route path="/support" element={<SupportPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route
            path="/playtest"
            element={isPlaytestHarnessEnabled ? <PlaytestPage /> : <Navigate to="/" replace />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <AuthModal />
        <ToastContainer />
      </div>
    </PageContainer>
  );
}

export default App;

