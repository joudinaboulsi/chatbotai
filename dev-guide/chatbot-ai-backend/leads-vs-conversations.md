# Conversations vs. Leads

Two of the most-used entities in the admin dashboard, and easy to conflate since every Lead
points at exactly one Conversation. This doc explains what each actually tracks, how one becomes
the other, and why the two are kept as separate tables/pages/archives instead of one.

## TL;DR

- **Conversation** = the raw chat session/transcript. Created the instant a visitor opens the
  widget, no matter what they talk about.
- **Lead** = a sales/follow-up record created *from* a conversation, but only when the visitor
  does something worth chasing (pricing question, demo request, buying intent, asks for a
  human, etc.). Not every conversation produces one.

## Conversation — the transcript

Model: `app/models/conversation.py::Conversation`. Table: `conversations`.

| Field | Purpose |
|---|---|
| `agent_id` | Which configured agent (bot persona) this chat belongs to. |
| `visitor_id` | The website visitor (`Visitor` — session-token identified, never authenticated). |
| `status` | The conversation's own lifecycle state (see below). |
| `assigned_operator_id` | Which human operator owns it once it's escalated. |
| `started_at`, `last_message_at` | Timestamps for sorting/"time ago" display. |
| `resolved_at` | Set when marked resolved (`POST /conversations/{id}/resolve`). |
| `archived_at` | Set when archived — independent of `status`, see "Archiving" below. |
| `messages` | The actual transcript — every `Message` row (visitor/ai/operator/system), ordered by `created_at`. |

**Status lifecycle** (`ConversationStatus` enum):

```
ai_active ──► waiting_for_agent ──► human_active ──► resolved
    │                                                    │
    └──────────────────────────────────────────────► closed
```

- `ai_active` — the bot is handling it (RAG answers, SMSC tool-calling, or the sales flow).
- `waiting_for_agent` — visitor asked for a human; sitting in the live-agent queue.
- `human_active` — an operator accepted it (`POST /conversations/{id}/assign`) and is replying
  directly (`POST /conversations/{id}/messages`).
- `resolved` / `closed` — done, either because the issue was fixed or the operator just closed
  it out.

**Every single widget interaction creates a Conversation** — someone who asks "what is SMPP?"
and leaves has a Conversation with a couple of messages in it and nothing else. There's no
qualification bar to clear.

## Lead — the follow-up record

Model: `app/models/lead.py::Lead`. Table: `leads`.

| Field | Purpose |
|---|---|
| `conversation_id` | The conversation this lead came from — **unique constraint**, so a conversation can produce at most one lead row (see "Idempotency" below). |
| `agent_id`, `visitor_id` | Denormalized copies from the conversation, for filtering without a join. |
| `name`, `email`, `phone`, `company` | Contact info, backfilled from the visitor as it becomes available (see below) — often starts out mostly `null`. |
| `source` | *Why* this became a lead — see the trigger table below. |
| `status` | The lead's own sales-pipeline stage — completely separate from the conversation's `status`. |
| `assigned_operator_id` | Which operator owns the follow-up (independent from who's handling the live chat). |
| `notes` | Freeform staff notes. |
| `archived_at` | Set when archived — independent of `status`, same pattern as conversations. |

**Status lifecycle** (`LeadStatus` enum) — a CRM funnel, not a chat state:

```
new ──► contacted ──► qualified ──► converted
                                 └─► closed
```

**What actually creates a Lead** (`app/services/lead_detection.py` + direct calls to
`create_or_get_lead`):

| `LeadSource` | Triggered by |
|---|---|
| `pricing_request` | Visitor's message contains "price"/"pricing"/"cost"/"how much"/"rates" |
| `demo_request` | "demo"/"demonstration"/"trial"/"try it out" |
| `quote_request` | "quote"/"quotation"/"estimate" |
| `purchase_request` | "buy"/"purchase"/"subscribe"/"sign up" |
| `contact_sales_request` | "talk to sales"/"contact sales"/"speak to sales", **or** clicking a Sales quick-reply button in the widget menu |
| `human_support_request` | "talk to a human"/"human agent"/"real person"/"live agent" — this is also what fires when a Live Agent handoff request is created (`handoff_service.py`) |
| `service_inquiry` | "what services"/"what do you offer" |
| `visitor_identified` | The public sales flow (`sales_ai_service.py`) successfully captures the visitor's name/phone via its `save_contact_info` tool — i.e. they became a real, named prospect, regardless of what they asked about |
| `manual` | Created via the widget's dedicated `POST /{agent_id}/lead` endpoint (e.g. an explicit "contact us" form) with no more specific source given |

Keyword matching (`detect_lead_source`) is deliberately simple substring matching on the
visitor's own message text — not an LLM call — so it's cheap to run on every message.

**Idempotency & backfill** (`lead_service.create_or_get_lead`): a lead is often created early —
the visitor asks "what's your pricing?" before giving a name — so the row starts with
`name`/`email`/`phone` all `null`. Every subsequent call for the *same conversation* doesn't
create a duplicate (the unique constraint on `conversation_id` would reject it anyway); instead
it backfills any still-`null` contact fields from the visitor's now-more-complete profile. This
is why a lead's contact info tends to fill in over the life of a conversation rather than
appearing complete on creation.

## The relationship

```
Conversation ──0 or 1──► Lead
     │
     └──< Message (many)
```

One-directional in practice: every `Lead.conversation_id` points at a real conversation, but
most conversations have **no** lead at all — only the subset where the visitor showed buying
intent, asked a support-worthy question, or got escalated to a human. A purely informational
"what is SMPP?" chat stays a Conversation forever and never becomes a Lead.

## Why they're archived separately

Both have their own independent `archived_at` column (see `dev-guide` migrations
`2007f60cdc51`/`a8a07ca2d401`) and their own Archive tab in the dashboard (`/archive` has a
Conversations sub-tab and a Leads sub-tab; `/leads` also has its own in-page Archived toggle).
Archiving one has no effect on the other — you might archive a Conversation once the chat is
truly over, while its Lead stays active in the sales pipeline for weeks of follow-up, or
vice versa (archive a dead-end Lead while keeping the transcript around for reference).

## Where each shows up in the UI

| | Conversations page (`/conversations`) | Leads page (`/leads`) |
|---|---|---|
| Filters | Status tabs (`ai_active`/`waiting_for_agent`/.../`closed`), has-lead, sort | Status tabs (`new`/`contacted`/.../`closed`), search |
| Row shows | Visitor, chat status dot, message count, last-message preview | Visitor, source badge, contact info, editable pipeline status |
| Primary action | Open the transcript, reply as an operator, resolve/close/archive | Change pipeline stage inline, jump to the underlying conversation, archive |
| Detail page | Full message-by-message transcript (`/conversations/:id`) | No separate detail page — "View" jumps straight to that lead's conversation |

This is also why the Leads page's "View" action links to `/conversations/{lead.conversation_id}`
rather than having its own detail view — the conversation transcript *is* the lead's detail
view; the Lead row is just the CRM metadata layered on top of it.
