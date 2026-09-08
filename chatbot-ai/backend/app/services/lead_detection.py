from app.models.enums import LeadSource

_KEYWORDS: list[tuple[LeadSource, list[str]]] = [
    (LeadSource.PRICING_REQUEST, ["price", "pricing", "cost", "how much", "rates"]),
    (LeadSource.DEMO_REQUEST, ["demo", "demonstration", "trial", "try it out"]),
    (LeadSource.QUOTE_REQUEST, ["quote", "quotation", "estimate"]),
    (LeadSource.PURCHASE_REQUEST, ["buy", "purchase", "subscribe", "sign up", "sign me up"]),
    (LeadSource.CONTACT_SALES_REQUEST, ["talk to sales", "contact sales", "sales team", "speak to sales"]),
    (
        LeadSource.HUMAN_SUPPORT_REQUEST,
        ["talk to a human", "human agent", "real person", "speak to someone", "customer support agent", "live agent"],
    ),
    (LeadSource.SERVICE_INQUIRY, ["what services", "what do you offer", "your services", "tell me about your services"]),
]


def detect_lead_source(text: str) -> LeadSource | None:
    lowered = text.lower()
    for source, keywords in _KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return source
    return None


def is_explicit_handoff_request(text: str) -> bool:
    source = detect_lead_source(text)
    return source == LeadSource.HUMAN_SUPPORT_REQUEST
