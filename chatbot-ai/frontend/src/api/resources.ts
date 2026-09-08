import { apiClient } from './client'
import type {
  Agent,
  AgentStatus,
  AuditLogEntry,
  Branding,
  ConversationDetail,
  ConversationListItem,
  ConversationStatus,
  DashboardCharts,
  DashboardStats,
  EmailSettings,
  KnowledgeBase,
  KnowledgeDocument,
  KnowledgeSourceType,
  Lead,
  LeadStatus,
  LiveAgentRequest,
  Message,
  NotificationOut,
  Operator,
  Paginated,
  ScrapedSite,
  ScrapeMode,
  SMSCSettings,
  UserOut,
  UserRole,
  UserStatus,
} from './types'

// --- Auth ---
export const authApi = {
  login: (email: string, password: string) => apiClient.post('/auth/login', { email, password }),
  me: () => apiClient.get<UserOut>('/auth/me'),
  logout: (refresh_token: string) => apiClient.post('/auth/logout', { refresh_token }),
}

// --- Agents ---
export interface AgentCreateInput {
  name: string
  company_name: string
  industry?: string
  description?: string
  remarks?: string
  languages?: string[]
  notification_email?: string
}

export const agentsApi = {
  list: (params: { search?: string; status?: AgentStatus; page?: number; page_size?: number }) =>
    apiClient.get<Paginated<Agent>>('/agents', { params }),
  get: (id: string) => apiClient.get<Agent>(`/agents/${id}`),
  create: (data: AgentCreateInput) => apiClient.post<Agent>('/agents', data),
  update: (id: string, data: Partial<AgentCreateInput>) => apiClient.put<Agent>(`/agents/${id}`, data),
  remove: (id: string) => apiClient.delete(`/agents/${id}`),
  duplicate: (id: string) => apiClient.post<Agent>(`/agents/${id}/duplicate`),
  activate: (id: string) => apiClient.post<Agent>(`/agents/${id}/activate`),
  deactivate: (id: string) => apiClient.post<Agent>(`/agents/${id}/deactivate`),
  embedCode: (id: string) => apiClient.get<{ embed_code: string }>(`/agents/${id}/embed-code`),
  getBranding: (id: string) => apiClient.get<Branding>(`/agents/${id}/branding`),
  updateBranding: (id: string, data: Partial<Branding>) => apiClient.put<Branding>(`/agents/${id}/branding`, data),
  uploadLogo: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<Branding>(`/agents/${id}/branding/logo`, form)
  },
  uploadAvatar: (id: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<Branding>(`/agents/${id}/branding/avatar`, form)
  },
  deleteLogo: (id: string) => apiClient.delete<Branding>(`/agents/${id}/branding/logo`),
}

// --- Knowledge Base ---
export const knowledgeApi = {
  list: () => apiClient.get<KnowledgeBase[]>('/knowledge-bases'),
  create: (data: { name: string; description?: string; source_type: KnowledgeSourceType; agent_ids: string[] }) =>
    apiClient.post<KnowledgeBase>('/knowledge-bases', data),
  get: (id: string) => apiClient.get<KnowledgeBase>(`/knowledge-bases/${id}`),
  update: (id: string, data: { name?: string; description?: string; agent_ids?: string[] }) =>
    apiClient.put<KnowledgeBase>(`/knowledge-bases/${id}`, data),
  remove: (id: string) => apiClient.delete(`/knowledge-bases/${id}`),
  uploadPdf: (kbId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return apiClient.post<KnowledgeDocument>(`/knowledge-bases/${kbId}/pdf`, form)
  },
  listDocuments: (kbId: string) => apiClient.get<KnowledgeDocument[]>(`/knowledge-bases/${kbId}/documents`),
  reprocessDocument: (kbId: string, docId: string) =>
    apiClient.post<KnowledgeDocument>(`/knowledge-bases/${kbId}/documents/${docId}/reprocess`),
  deleteDocument: (kbId: string, docId: string) => apiClient.delete(`/knowledge-bases/${kbId}/documents/${docId}`),
  createScrape: (
    kbId: string,
    data: {
      url: string
      mode: ScrapeMode
      max_pages: number
      max_depth: number
      include_subpages: boolean
      exclude_urls: string[]
    },
  ) => apiClient.post<ScrapedSite>(`/knowledge-bases/${kbId}/scrape`, data),
  listScrapedSites: (kbId: string) => apiClient.get<ScrapedSite[]>(`/knowledge-bases/${kbId}/scraped-sites`),
  rescrape: (kbId: string, siteId: string) =>
    apiClient.post<ScrapedSite>(`/knowledge-bases/${kbId}/scraped-sites/${siteId}/rescrape`),
  deleteScrapedSite: (kbId: string, siteId: string) =>
    apiClient.delete(`/knowledge-bases/${kbId}/scraped-sites/${siteId}`),
}

// --- Conversations ---
export const conversationsApi = {
  list: (params: { agent_id?: string; status?: ConversationStatus; page?: number; page_size?: number }) =>
    apiClient.get<Paginated<ConversationListItem>>('/conversations', { params }),
  get: (id: string) => apiClient.get<ConversationDetail>(`/conversations/${id}`),
  sendMessage: (id: string, content: string) => apiClient.post<Message>(`/conversations/${id}/messages`, { content }),
  resolve: (id: string) => apiClient.post<ConversationListItem>(`/conversations/${id}/resolve`),
  close: (id: string) => apiClient.post<ConversationListItem>(`/conversations/${id}/close`),
  assign: (id: string) => apiClient.post<ConversationListItem>(`/conversations/${id}/assign`),
}

// --- Leads ---
export const leadsApi = {
  list: (params: { agent_id?: string; status?: LeadStatus; page?: number; page_size?: number }) =>
    apiClient.get<Paginated<Lead>>('/leads', { params }),
  get: (id: string) => apiClient.get<Lead>(`/leads/${id}`),
  update: (id: string, data: Partial<Pick<Lead, 'status' | 'assigned_operator_id' | 'notes' | 'company'>>) =>
    apiClient.put<Lead>(`/leads/${id}`, data),
}

// --- Live Agents ---
export const liveAgentsApi = {
  list: (status?: string) => apiClient.get<LiveAgentRequest[]>('/live-agents', { params: { status } }),
  assign: (id: string) => apiClient.post<LiveAgentRequest>(`/live-agents/${id}/assign`),
  resolve: (id: string) => apiClient.post<LiveAgentRequest>(`/live-agents/${id}/resolve`),
}

// --- Operators ---
export interface OperatorCreateInput {
  name: string
  email: string
  password: string
  role: UserRole
  assigned_agent_ids: string[]
}

export const operatorsApi = {
  list: () => apiClient.get<Operator[]>('/operators'),
  create: (data: OperatorCreateInput) => apiClient.post<Operator>('/operators', data),
  update: (
    id: string,
    data: Partial<{ name: string; role: UserRole; status: UserStatus; assigned_agent_ids: string[] }>,
  ) => apiClient.put<Operator>(`/operators/${id}`, data),
  remove: (id: string) => apiClient.delete(`/operators/${id}`),
}

// --- Notifications ---
export const notificationsApi = {
  list: (unreadOnly = false) => apiClient.get<NotificationOut[]>('/notifications', { params: { unread_only: unreadOnly } }),
  markRead: (id: string) => apiClient.post<NotificationOut>(`/notifications/${id}/read`),
  markAllRead: () => apiClient.post('/notifications/read-all'),
}

// --- Settings ---
export const settingsApi = {
  getEmail: () => apiClient.get<EmailSettings>('/settings/email'),
  updateEmail: (data: Partial<EmailSettings> & { smtp_password?: string }) =>
    apiClient.put<EmailSettings>('/settings/email', data),
  testEmail: (to_email: string) => apiClient.post('/settings/email/test', { to_email }),
}

export const smscSettingsApi = {
  get: () => apiClient.get<SMSCSettings>('/settings/smsc'),
  update: (data: Partial<SMSCSettings> & { api_key?: string }) =>
    apiClient.put<SMSCSettings>('/settings/smsc', data),
  test: () => apiClient.post<{ connected: boolean; detail: string }>('/settings/smsc/test'),
}

// --- Dashboard ---
export const dashboardApi = {
  stats: (agent_id?: string) => apiClient.get<DashboardStats>('/dashboard/stats', { params: { agent_id } }),
  charts: (agent_id?: string, days = 30) => apiClient.get<DashboardCharts>('/dashboard/charts', { params: { agent_id, days } }),
}

// --- Audit Logs ---
export const auditApi = {
  list: (params: { page?: number; page_size?: number }) =>
    apiClient.get<Paginated<AuditLogEntry>>('/audit-logs', { params }),
}
