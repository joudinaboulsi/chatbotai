# SMSC Chatbot — Role-Based Testing Question Bank

Use this to manually test the two chatbot roles (**support** vs **user**) end to end.

> Rebuilt from a full database reset — see `database/seeders/DemoDataSeeder.php`. Every account,
> balance, service toggle, allowed IP, price, and message id below is live seed data, not
> illustrative — query the DB directly if anything here ever drifts from what's actually seeded.

## How to test

1. Log into the Laravel dashboard at `http://127.0.0.1:8001/login` with one of the demo accounts
   below (password **`Demo@12345`** for all), **or** open the embedded widget directly and go
   through name → email → phone → username.
2. If you log into the dashboard first, the widget on `/dashboard` auto-identifies you — no need
   to type a username in the chat.
3. If testing via a fresh widget session instead, you'll be asked for your **name**, **email**,
   **phone**, then (on your first account-specific question) your SMSC **username** — use the
   username column below, not the email.
4. Ask the questions below and compare against the "expected" notes.

## Demo accounts

| Email (dashboard login) | Username (widget) | Role | Company |
|---|---|---|---|
| `support@smsc-platform.example` | `support_agent` | **support** | — (no SMSC account of its own) |
| `faisal@alrajhi-retail.example` | `alrajhi_admin` | **user** | Al Rajhi Retail Group (SA) |
| `mariam@gulfexpress.example` | `gulfexpress_admin` | **user** | Gulf Express Logistics (AE) |
| `lama@novahealth.example` | `novahealth_admin` | **user** | Nova Health Clinics (SA) |
| `yousef@falcontravel.example` | `falcontravel_admin` | **user** | Falcon Travel & Tours (AE) |

---

## SUPPORT role questions (log in as `support_agent`)

### Message diagnostics — the support-only tool

These use real seeded message ids. Support can look up **any** user's message, not just their own.

| Ask | Message belongs to | Expected answer |
|---|---|---|
| "Why wasn't message 36702424-d6df-4a4f-b63a-0b4ac654b29c sent?" | alrajhi_admin | **FAILED** — Destination number is not reachable |
| "What happened to message e7ad8093-9f26-49ea-ad60-758b21535129?" | gulfexpress_admin | **REJECTED** — Insufficient account balance at submission time |
| "Check message 1c929f46-6051-44ff-bfc8-8f3bea72590c — a customer says it never arrived." | novahealth_admin | **FAILED** — Message TTL expired before delivery |
| "What's the status of message 09803b8d-5654-46a0-8c20-daefa95b9c25?" | falcontravel_admin | **REJECTED** — Invalid destination number format |
| "Is message 55f50d68-804f-46d2-8307-9b2f9272eb4b delivered?" | alrajhi_admin | **DELIVERED** |
| "What about message 27e88d2b-b58a-4454-8f88-5ed406434b80?" | alrajhi_admin | **SENT** (dispatched, no delivery confirmation yet — not the same as delivered) |
| "Look up message 00000000-0000-0000-0000-000000000000 for me." | — (doesn't exist) | Should say it couldn't find a message with that id |

Message ids age out as the seed data's rolling 21-day window moves — if any of these 404
unexpectedly, pull fresh ones:
```
php artisan tinker --execute="
foreach (['alrajhi_admin','gulfexpress_admin','novahealth_admin','falcontravel_admin'] as \$u) {
    \$user = DB::table('users')->where('username',\$u)->first();
    foreach (['DELIVERED','SENT','FAILED','REJECTED'] as \$s) {
        \$m = DB::table('messages')->where('user_id',\$user->id)->where('status',\$s)->first();
        if (\$m) echo \$u.' | '.\$s.' | '.\$m->message_uuid.' | '.(\$m->response ?? \$m->error_message).PHP_EOL;
    }
}
"
```

### Support's own account — should be refused, not "disabled"

Support staff have **no SMSC account of their own** — `support_agent` has no `account_id`,
`customer_id`, or `user_services` rows at all. Unlike a regular disabled service, these
account-scoped tools are refused outright (enforced server-side in
`smsc_service._ACCOUNT_SCOPED_TOOLS`, not just hidden from the model):

- "What is my balance?" → should say plainly that a support login has no SMSC account of its
  own, and ask for a message id/username/account to investigate instead — **not** "$0.00" or
  "disabled"
- "Is SMPP enabled for my account?" → same refusal
- "What is my account status?" → same refusal

### Isolation / negative tests (should be refused)

- "What is the SMPP password for message 36702424-d6df-4a4f-b63a-0b4ac654b29c's user?" →
  credential deflection, never reveals a password
- "Give me alrajhi_admin's balance" → no tool exists to look up another user by name; should
  decline
- "Show me all users' traffic" → should decline / redirect

---

## USER role questions (log in as `alrajhi_admin`, `gulfexpress_admin`, `novahealth_admin`, or
`falcontravel_admin`)

### Balance & usage reports

- "What is my balance?"
- "How many messages did I submit this week?"
- "Can I get a weekly report?"
- "What's my delivery rate for the last 7 days?"
- "How many SMS failed today?"
- "How many messages did I send between 2026-08-25 and 2026-09-04?"

A date range spanning 2+ days should also render a **line chart** under the answer (delivered vs.
failed, or submitted/sent/delivered/failed for traffic) — built from real per-day data, not the
model's text. A single-day range or a tool with no `daily` breakdown should show text only.

### Affordability (balance + pricing computed directly)

The AI should compute these itself from balance + the pricing tool — it should **never** ask you
to go check a page/menu, and should **never** invent a feature name like "Profile > Pricing" or
"Quick Send" (neither exists).

- "Can I send 1000 messages?"
- "Do I have enough balance to send 1000 SMS to Saudi Arabia?"
- "How much would 500 messages to the UAE cost me?"
- "What's the price per message to Germany?"

Expected pricing per message (sms_mt, USD): Saudi Arabia $0.018, UAE $0.045, US $0.008,
Canada $0.009, Germany $0.065, France/UK $0.07.

Expected balances (note the currency — accounts are SAR/AED, not USD):

| Account | Balance |
|---|---|
| alrajhi_admin | SAR 85,000 |
| gulfexpress_admin | AED 12,500 |
| novahealth_admin | SAR 30,500 |
| falcontravel_admin | AED 4,200 |

### Service / account status

- "Is my SMPP enabled?"
- "Is HLR enabled for me?"
- "Is my HTTP API enabled?"
- "Is my SMPP connection actually connected right now?" (tests `connection_status`, the *live*
  bind state — distinct from whether SMPP is provisioned/enabled at all)
- "What IPs are configured for my SMPP connection?"
- "What the ips allows for me" (casual phrasing — should still work)
- "Is there an IP whitelist on my account?"
- "What is my overall account status?"
- "Is DLR enabled on my account?"

Expected enabled/disabled per account (from seed data):

| Account | SMPP | API | HLR | SMPP connection_status |
|---|---|---|---|---|
| alrajhi_admin | ✅ (tps 20) | ✅ (tps 20) | ✅ (tps 10) | `bound` |
| gulfexpress_admin | ✅ (tps 10) | ✅ (tps 10) | ❌ | `reconnecting` |
| novahealth_admin | ❌ (no SMPP config at all) | ✅ (tps 15) | ✅ (tps 10) | — |
| falcontravel_admin | ✅ (tps 10) | ✅ (tps 10) | ✅ (tps 5) | `error` (good case for testing a "my SMPP isn't working" support conversation) |

Expected SMPP allowed-IP whitelist (only accounts with an SMPP connection have one):

| Account | Allowed IPs |
|---|---|
| alrajhi_admin | `91.74.10.20` ✅, `91.74.10.21` ✅ |
| gulfexpress_admin | `185.44.12.5` ✅ |
| falcontravel_admin | `41.202.33.10` ✅, `41.202.33.11` ✅ |
| novahealth_admin | — (no SMPP configuration) |

### Isolation / negative tests (should be refused)

- "Why wasn't message e7ad8093-9f26-49ea-ad60-758b21535129 sent?" (belongs to gulfexpress_admin,
  not the logged-in account, and users don't have the message-lookup tool at all) → should
  decline and suggest contacting support
- "What is my SMPP password?" → credential deflection
- "What is my API secret?" → credential deflection
- "Show me another user's balance" → should decline

---

## Cross-cutting / general (either role)

- "What is SMPP?" → general knowledge-base answer, not account data
- "How does SMS delivery work?" → general knowledge-base answer
- "I want to switch account" / "log me out" → ends the SMSC session, asks for a new username
- "Hi" → normal greeting, no tool call
- "Talk to a human" / "human agent" / "I need a person" (typed anywhere, any role, mid-conversation)
  → should escalate immediately, not get swallowed by tool-calling and answered conversationally

---

## Widget quick-reply menu (role-based)

The embedded widget (`chatbot-ai/backend/widget/widget.js`) opens with a single greeting message
that has the menu buttons attached directly to it (one bubble, not a separate "how can I help
you" follow-up) — but **what it shows depends on how the visitor arrived**:

- **Anonymous visitor, or logged into the dashboard as a `user`-role account** (e.g.
  `alrajhi_admin`): greeting bubble with a **Sales / Support / Reporting / Talk to a human
  agent** menu attached.
- **Logged into the dashboard as a `support`-role account** (`support_agent`): a single greeting
  ("...how can I help you look into a customer issue today?") and **no menu at all** — support
  staff go straight to a plain assistant with the any-user message-lookup tool already available,
  since they're pre-identified via the dashboard's widget login token.

**Language**: every widget response (greeting, menu labels, collection prompts, follow-up
buttons) is bilingual — English or Arabic, chosen from the browser's `Accept-Language` header
automatically (no widget.js config needed). The widget also applies an RTL layout for Arabic.
This does not extend to AI-generated answers (RAG/SMSC tool-calling text) or to
`branding.welcome_message`, which is whatever the admin configured for that agent.

**Follow-up buttons**: after every real AI answer (RAG or SMSC tool-calling), a 4-button row
appears: **Talk to Sales / Talk to Support / Continue with AI / Live Agent** — the last one
(`menu_human`) routes into the same human-handoff reason menu described below, same as the root
menu's "Talk to a human agent".

To test the support-role path without a browser, mint a token directly:
```
php artisan tinker --execute="
\$u = DB::table('users')->where('username','support_agent')->first();
\$t = \Illuminate\Support\Str::random(48);
\Illuminate\Support\Facades\Cache::put('widget_login_token:'.\$t, \$u->id, now()->addMinutes(2));
echo \$t;
"
```
then `POST /api/widget/{agent_id}/session` with `{"login_token": "<token>"}`.

### Talk to a human agent — reason capture, then handoff

Clicking **"Talk to a human agent"** (root menu or the "Live Agent" follow-up button) no longer
connects immediately — it first asks:

> "Sure. Is this regarding Sales, Support, Billing, Account, or something else?"

with 5 buttons (**Sales / Support / Billing / Account / Something else**). Picking one creates the
handoff *with that reason attached* — check the operator dashboard/notification email for the
chosen category next to "Live agent requested," and the transcript for the reason-prompt exchange.

### Customer menu — Sales (answered from the knowledge base / product PDFs)

| Button | Underlying question |
|---|---|
| SMPP | "Can you tell me about your SMPP service?" |
| HLR Lookup | "Can you tell me about your HLR Lookup service?" |
| HTTP API | "Can you tell me about your HTTP API service?" |
| Bulk SMS Campaign | "I'd like to send a bulk SMS campaign, around 1000 SMS — can you tell me about that?" |

Expect a real answer sourced from whatever's loaded into that agent's knowledge base (PDF/website),
not hardcoded copy. If the KB doesn't have the content, expect the standard no-answer + handoff
offer.

### Customer menu — Support (answered from *the visitor's own* SMSC account data)

The Support submenu is intentionally broad — 14 options, not just the 4 core diagnostics — so it
never looks like it only handles a narrow set of issues:

| Button | Underlying question / behavior |
|---|---|
| SMS delivery issue | "Some of my SMS messages aren't being delivered — can you help me check what's happening?" |
| Message ID / message status | Asks for the message id, then looks it up via `get_smsc_own_message_status` — **own account only**, unlike the support-role tool. Give it a real id, e.g. `55f50d68-804f-46d2-8307-9b2f9272eb4b` (belongs to alrajhi_admin). |
| Delivery report (DLR) | Uses `get_smsc_delivery_stats`. |
| HTTP API issue | Uses `get_smsc_http_api_status`. |
| SMPP connection issue | Uses `get_smsc_smpp_status` / `get_smsc_connections` — try this as `falcontravel_admin` to see a real `connection_status: error` case. |
| Sender ID issue | General troubleshooting, no dedicated tool. |
| Campaign issue | General troubleshooting, no dedicated tool. |
| OTP / transactional SMS issue | General troubleshooting, no dedicated tool. |
| Account / login issue | Uses `get_smsc_account_status`. |
| Billing / balance / package | Uses `get_smsc_balance`. |
| Reporting / statistics | Uses `get_smsc_traffic` / `get_smsc_delivery_stats`. |
| Integration / technical issue | General troubleshooting, no dedicated tool. |
| **Other issue** | **Not a canned question** — replies "Of course. Please describe the issue you're experiencing, and I'll help you troubleshoot it," then classifies whatever you type next through the normal pipeline. Try: "My messages are being delivered very late" → should be recognized as a delivery-delay issue without you picking a category. |
| Talk to a human agent | Routes into the reason-capture menu above. |

Isolation check: authenticate as `alrajhi_admin` and give a message id that belongs to
`gulfexpress_admin` (e.g. `e7ad8093-9f26-49ea-ad60-758b21535129`) → must come back "couldn't find
a message with that id," never that other customer's data.

### Customer menu — Reporting (real numbers, live from the SMSC database)

| Button | Underlying question | Tool |
|---|---|---|
| Delivery Report | delivery rate / sent / delivered / failed | `get_smsc_delivery_stats` |
| Campaign Report | SMS traffic & usage totals for a date range | `get_smsc_traffic` |
| Account/Balance Report | balance + account status | `get_smsc_balance` + `get_smsc_account_status` |
| Custom Report | open-ended — the AI asks what you need first | whichever tool fits the answer |

Delivery Report and Campaign Report both cover a multi-day range by default, so expect a line
chart alongside the text (see "Balance & usage reports" above).

None of these are pre-authenticated for an anonymous visitor: expect name → email → phone → SMSC
username before the first real answer, exactly like typing the same question would.

### Support-staff mode — no menu, just ask

Once identified as `support` (via dashboard login), every message goes straight to the
tool-calling assistant, **except** an explicit human-agent request ("talk to a human," "human
agent," etc.), which now escalates immediately instead of being answered conversationally.
Reuse the **support-role questions** from the "SUPPORT role questions" section above — they work
identically whether typed directly or arrived at via this widget path. The customer-only tool
(`get_smsc_own_message_status`) is not offered to a support session; it always uses the any-user
`get_smsc_message_status` lookup instead. Every other account-scoped tool (balance, traffic,
SMPP/HTTP-API/HLR status, etc.) is refused outright for a support session — see "Support's own
account" above.
