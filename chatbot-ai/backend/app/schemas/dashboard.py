from datetime import date

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_conversations: int
    active_conversations: int
    new_leads: int
    leads_today: int
    leads_this_week: int
    leads_this_month: int
    live_agent_requests_waiting: int
    resolved_conversations: int
    average_response_time_seconds: float | None


class DailyCount(BaseModel):
    day: date
    count: int


class StatusCount(BaseModel):
    status: str
    count: int


class DashboardCharts(BaseModel):
    conversations_over_time: list[DailyCount]
    leads_over_time: list[DailyCount]
    ai_vs_human_conversations: list[StatusCount]
    conversation_status_breakdown: list[StatusCount]
