import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { RequireAuth } from './components/RequireAuth'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { AgentCreatePage } from './pages/AgentCreatePage'
import { AgentsPage } from './pages/AgentsPage'
import { ArchivePage } from './pages/ArchivePage'
import { ConversationDetailPage } from './pages/ConversationDetailPage'
import { ConversationsPage } from './pages/ConversationsPage'
import { DashboardPage } from './pages/DashboardPage'
import { KnowledgeBasePage } from './pages/KnowledgeBasePage'
import { LeadsPage } from './pages/LeadsPage'
import { LiveAgentsPage } from './pages/LiveAgentsPage'
import { LoginPage } from './pages/LoginPage'
import { OperatorsPage } from './pages/OperatorsPage'
import { ProfilePage } from './pages/ProfilePage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/new" element={<AgentCreatePage />} />
        <Route path="/agents/:id" element={<AgentDetailPage />} />
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="/conversations" element={<ConversationsPage />} />
        <Route path="/conversations/:id" element={<ConversationDetailPage />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/archive" element={<ArchivePage />} />
        <Route path="/live-agents" element={<LiveAgentsPage />} />
        <Route path="/operators" element={<OperatorsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
