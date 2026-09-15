export type UserRole = 'super_admin' | 'admin' | 'support_agent'
export type UserStatus = 'active' | 'inactive'
export type AgentStatus = 'active' | 'inactive'
export type AgentChannel = 'web' | 'whatsapp'
export type WidgetPosition = 'bottom_right' | 'bottom_left'
export type WidgetSize = 'standard' | 'compact' | 'large'
export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type ScrapeMode = 'single_url' | 'crawl'
export type ConversationStatus = 'ai_active' | 'waiting_for_agent' | 'human_active' | 'resolved' | 'closed'
export type MessageSender = 'visitor' | 'ai' | 'operator' | 'system'
export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'converted' | 'closed'
export type LeadSource =
  | 'pricing_request'
  | 'demo_request'
  | 'quote_request'
  | 'purchase_request'
  | 'service_inquiry'
  | 'contact_sales_request'
  | 'human_support_request'
  | 'visitor_identified'
  | 'manual'
export type LiveAgentRequestStatus = 'waiting' | 'assigned' | 'active' | 'resolved' | 'closed'
export type NotificationType =
  | 'new_lead'
  | 'live_agent_request'
  | 'new_conversation'
  | 'kb_processing_failed'
  | 'email_failed'
  | 'system_error'
export type SmtpEncryption = 'none' | 'ssl' | 'tls'
export type SmscAuthScheme = 'api_key' | 'bearer'

export interface UserOut {
  id: string
  name: string
  email: string
  role: UserRole
  status: UserStatus
}

export interface Agent {
  id: string
  name: string
  company_name: string
  industry: string | null
  description: string | null
  remarks: string | null
  languages: string[]
  status: AgentStatus
  channel: AgentChannel
  notification_email: string | null
  created_at: string
  updated_at: string
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Branding {
  agent_id: string
  logo_url: string | null
  avatar_url: string | null
  primary_color: string
  secondary_color: string
  background_color: string
  text_color: string
  button_color: string
  font_family: string
  font_size: string
  widget_position: WidgetPosition
  widget_size: WidgetSize
  welcome_message: string
  placeholder_text: string
  display_company_name: string | null
  display_agent_name: string | null
}

export type KnowledgeSourceType = 'pdf' | 'website'

export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  source_type: KnowledgeSourceType
  agent_ids: string[]
  created_at: string
}

export interface KnowledgeDocument {
  id: string
  file_name: string
  file_size_bytes: number
  status: ProcessingStatus
  chunk_count: number
  error_message: string | null
  created_at: string
  processed_at: string | null
}

export interface ScrapedSite {
  id: string
  base_url: string
  mode: ScrapeMode
  max_pages: number
  max_depth: number
  include_subpages: boolean
  exclude_urls: string[]
  status: ProcessingStatus
  pages_discovered: number
  pages_processed: number
  error_message: string | null
  last_scraped_at: string | null
  created_at: string
}

export interface ConversationListItem {
  id: string
  agent_id: string
  visitor_name: string | null
  visitor_email: string | null
  visitor_phone: string | null
  status: ConversationStatus
  assigned_operator_id: string | null
  started_at: string
  last_message_at: string | null
  message_count: number
  last_message_preview: string | null
  archived_at: string | null
}

export interface PaginatedConversations extends Paginated<ConversationListItem> {
  status_counts: Record<ConversationStatus, number>
}

export interface Message {
  id: string
  sender_type: MessageSender
  sender_user_id: string | null
  content: string
  message_metadata: Record<string, unknown>
  created_at: string
}

export interface ConversationDetail extends ConversationListItem {
  messages: Message[]
}

export interface Lead {
  id: string
  agent_id: string
  visitor_id: string
  conversation_id: string
  name: string | null
  email: string | null
  phone: string | null
  company: string | null
  source: LeadSource
  status: LeadStatus
  assigned_operator_id: string | null
  notes: string | null
  created_at: string
  archived_at: string | null
}

export interface PaginatedLeads extends Paginated<Lead> {
  status_counts: Record<LeadStatus, number>
}

export interface LiveAgentRequest {
  id: string
  conversation_id: string
  visitor_id: string
  agent_id: string
  status: LiveAgentRequestStatus
  assigned_operator_id: string | null
  requested_at: string
  assigned_at: string | null
  resolved_at: string | null
}

export interface Operator {
  id: string
  name: string
  email: string
  role: UserRole
  status: UserStatus
  assigned_agent_ids: string[]
  last_login_at: string | null
  created_at: string
}

export interface NotificationOut {
  id: string
  type: NotificationType
  title: string
  body: string | null
  resource_type: string | null
  resource_id: string | null
  link: string | null
  is_read: boolean
  created_at: string
}

export interface EmailSettings {
  smtp_host: string | null
  smtp_port: number
  smtp_username: string | null
  encryption: SmtpEncryption
  from_name: string | null
  from_email: string | null
  support_email: string | null
  is_configured: boolean
}

export interface SMSCSettings {
  enabled: boolean
  api_base_url: string | null
  auth_scheme: SmscAuthScheme
  timeout_seconds: number
  session_expire_minutes: number
  is_configured: boolean
}

export interface DashboardStats {
  total_conversations: number
  active_conversations: number
  new_leads: number
  leads_today: number
  leads_this_week: number
  leads_this_month: number
  live_agent_requests_waiting: number
  resolved_conversations: number
  average_response_time_seconds: number | null
}

export interface DailyCount {
  day: string
  count: number
}

export interface StatusCount {
  status: string
  count: number
}

export interface DashboardCharts {
  conversations_over_time: DailyCount[]
  leads_over_time: DailyCount[]
  ai_vs_human_conversations: StatusCount[]
  conversation_status_breakdown: StatusCount[]
}

export interface AuditLogEntry {
  id: string
  user_id: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  ip_address: string | null
  details: Record<string, unknown>
  created_at: string
}
