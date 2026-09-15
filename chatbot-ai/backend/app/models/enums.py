import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SUPPORT_AGENT = "support_agent"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AgentChannel(str, enum.Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"


class WidgetPosition(str, enum.Enum):
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"


class WidgetSize(str, enum.Enum):
    STANDARD = "standard"
    COMPACT = "compact"
    LARGE = "large"


class KnowledgeSourceType(str, enum.Enum):
    PDF = "pdf"
    WEBSITE = "website"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeMode(str, enum.Enum):
    SINGLE_URL = "single_url"
    CRAWL = "crawl"


class ConversationStatus(str, enum.Enum):
    AI_ACTIVE = "ai_active"
    WAITING_FOR_AGENT = "waiting_for_agent"
    HUMAN_ACTIVE = "human_active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MessageSender(str, enum.Enum):
    VISITOR = "visitor"
    AI = "ai"
    OPERATOR = "operator"
    SYSTEM = "system"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    CLOSED = "closed"


class LeadSource(str, enum.Enum):
    PRICING_REQUEST = "pricing_request"
    DEMO_REQUEST = "demo_request"
    QUOTE_REQUEST = "quote_request"
    PURCHASE_REQUEST = "purchase_request"
    SERVICE_INQUIRY = "service_inquiry"
    CONTACT_SALES_REQUEST = "contact_sales_request"
    HUMAN_SUPPORT_REQUEST = "human_support_request"
    VISITOR_IDENTIFIED = "visitor_identified"
    MANUAL = "manual"


class LiveAgentRequestStatus(str, enum.Enum):
    WAITING = "waiting"
    ASSIGNED = "assigned"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CLOSED = "closed"


class NotificationType(str, enum.Enum):
    NEW_LEAD = "new_lead"
    VISITOR_IDENTIFIED = "visitor_identified"
    LIVE_AGENT_REQUEST = "live_agent_request"
    NEW_CONVERSATION = "new_conversation"
    KB_PROCESSING_FAILED = "kb_processing_failed"
    EMAIL_FAILED = "email_failed"
    SYSTEM_ERROR = "system_error"


class SmtpEncryption(str, enum.Enum):
    NONE = "none"
    SSL = "ssl"
    TLS = "tls"


class SmscAuthScheme(str, enum.Enum):
    API_KEY = "api_key"
    BEARER = "bearer"


class SmscSessionStatus(str, enum.Enum):
    # A conversation asked something account-specific and we're waiting for
    # the visitor to reply with their SMSC username.
    PENDING = "pending"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    TERMINATED = "terminated"
