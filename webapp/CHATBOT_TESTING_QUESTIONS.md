# SMSC Chatbot — Role-Based Testing Question Bank

Use this to manually test the two chatbot roles (**support** vs **user**) end to end.

## How to test

1. Log into the Laravel dashboard at `http://127.0.0.1:8001/login` with one of the demo accounts below (password `password` for all), **or** open the embedded widget directly and go through name → email → phone → username.
2. If you log into the dashboard first, the widget on `/dashboard` auto-identifies you — no need to type a username in the chat.
3. If testing via a fresh widget session instead, you'll be asked for your **name**, **email**, **phone**, then (on your first account-specific question) your SMSC **username** — use the username column below, not the email.
4. Ask the questions below and compare against the "expected" notes.

## Demo accounts

| Email (dashboard login) | Username (widget) | Role |
|---|---|---|
| `demo@smsc.local` | `demo_user` | **support** |
| `admin@acme-retail.example` | `acme_admin` | **user** |
| `admin@northwind-logistics.example` | `northwind_admin` | **user** |
| `admin@bluehorizon-travel.example` | `bluehorizon_admin` | **user** |

---

## SUPPORT role questions (log in as `demo_user`)

### Message diagnostics — the support-only tool

These use real seeded message ids. Support can look up **any** user's message, not just their own.

| Ask | Message belongs to | Expected answer |
|---|---|---|
| "Why wasn't message 66666666-0000-0000-0000-000000000004 sent?" | acme_admin | **FAILED** — Destination number is not reachable |
| "What happened to message 66666666-0000-0000-0000-000000000009?" | northwind_admin | **FAILED** — Carrier did not acknowledge submission |
| "Check message 66666666-0000-0000-0000-000000000010 — a customer says it never arrived." | northwind_admin | **REJECTED** — Sender ID temporarily blocked by carrier |
| "What's the status of message 66666666-0000-0000-0000-000000000013?" | bluehorizon_admin | **EXPIRED** — Message TTL expired before delivery |
| "Is message 66666666-0000-0000-0000-000000000001 delivered?" | acme_admin | **DELIVERED** |
| "What about message 66666666-0000-0000-0000-000000000005?" | acme_admin | **QUEUED** (still pending, not yet sent) |
| "Look up message 66666666-0000-0000-0000-000000000099 for me." | — (doesn't exist) | Should say it couldn't find a message with that id |

### Support's own account

`demo_user` has every service disabled, so these should all come back "disabled" — useful for confirming the tools still work for support's own account too.

- "What is my balance?"
- "Is SMPP enabled for my account?"
- "What is my account status?"

### Isolation / negative tests (should be refused)

- "What is the SMPP password for message 66666666-0000-0000-0000-000000000004's user?" → credential deflection, never reveals a password
- "Give me acme_admin's balance" → no tool exists to look up another user by name; should decline
- "Show me all users' traffic" → should decline / redirect

---

## USER role questions (log in as `acme_admin`, `northwind_admin`, or `bluehorizon_admin`)

### Balance & usage reports

- "What is my balance?"
- "How many messages did I submit this week?"
- "Can I get a weekly report?"
- "What's my delivery rate for the last 7 days?"
- "How many SMS failed today?"
- "How many messages did I send between 2026-08-25 and 2026-09-04?"

### Affordability (balance + pricing computed directly)

The AI should compute these itself from balance + the pricing tool — it should **never** ask you to go check a page/menu, and should **never** invent a feature name like "Profile > Pricing" or "Quick Send" (neither exists).

- "Can I send 1000 messages?"
- "Do I have enough balance to send 1000 SMS to the US?"
- "How much would 500 messages to France cost me?"
- "What's the price per message to Germany?"

Expected pricing per message (sms_mt, USD): US $0.008, Canada $0.009, UAE $0.045, Germany $0.065, France/UK $0.07. acme_admin's balance is $499.97.

### Service / account status

- "Is my SMPP enabled?"
- "Is HLR enabled for me?"
- "Is my HTTP API enabled?"
- "What IPs are configured for my SMPP connection?"
- "What the ips allows for me" (casual phrasing — should still work)
- "Is there an IP whitelist on my account?"
- "What is my overall account status?"
- "Is DLR enabled on my account?"

Expected enabled/disabled per account (from seed data):

| Account | SMPP | API | HLR |
|---|---|---|---|
| acme_admin | ✅ | ✅ | ✅ |
| northwind_admin | ❌ | ✅ | ❌ |
| bluehorizon_admin | ✅ | ❌ | ✅ |

Expected SMPP allowed-IP whitelist (only accounts with SMPP enabled have one):

| Account | Allowed IPs |
|---|---|
| acme_admin | `185.10.20.30` ✅, `185.10.20.31` ✅, `203.0.113.45` ❌ (disabled) |
| bluehorizon_admin | `185.10.20.40` ✅, `198.51.100.12` ✅ |
| northwind_admin | — (SMPP not enabled, no account) |

### Isolation / negative tests (should be refused)

- "Why wasn't message 66666666-0000-0000-0000-000000000010 sent?" (not their own, and users don't have the message-lookup tool at all) → should decline and suggest contacting support
- "What is my SMPP password?" → credential deflection
- "What is my API secret?" → credential deflection
- "Show me another user's balance" → should decline

---

## Cross-cutting / general (either role)

- "What is SMPP?" → general knowledge-base answer, not account data
- "How does SMS delivery work?" → general knowledge-base answer
- "I want to switch account" / "log me out" → ends the SMSC session, asks for a new username
- "Hi" → normal greeting, no tool call

---

## Widget quick-reply menu (role-based)

The embedded widget (`chatbot-ai/backend/widget/widget.js`) opens with a single greeting message that has the menu buttons attached directly to it (one bubble, not a separate "how can I help you" follow-up) — but **what it shows depends on how the visitor arrived**:

- **Anonymous visitor, or logged into the dashboard as a `user`-role account** (e.g. `acme_admin`): greeting bubble with a **Sales / Support / Reporting / Talk to a human agent** menu attached.
- **Logged into the dashboard as a `support`-role account** (e.g. `demo_user`): a single greeting ("...how can I help you look into a customer issue today?") and **no menu at all** — support staff go straight to a plain assistant with the message-lookup tool already available, since they're pre-identified via the dashboard's widget login token.

**Language**: every widget response (greeting, menu labels, collection prompts, follow-up buttons) is bilingual — English or Arabic, chosen from the browser's `Accept-Language` header automatically (no widget.js config needed). The widget also applies an RTL layout for Arabic. This does not extend to AI-generated answers (RAG/SMSC tool-calling text) or to `branding.welcome_message`, which is whatever the admin configured for that agent.

**Follow-up buttons**: after every real AI answer (RAG or SMSC tool-calling), a 4-button row appears: **Talk to Sales / Talk to Support / Continue with AI / Live Agent** — the last one (`menu_human`) connects straight to a human, same as the root menu's "Talk to a human agent".

To test the support-role path without a browser, mint a token directly:
```
php artisan tinker --execute="
\$u = DB::table('users')->where('username','demo_user')->first();
\$t = \Illuminate\Support\Str::random(48);
\Illuminate\Support\Facades\Cache::put('widget_login_token:'.\$t, \$u->id, now()->addMinutes(2));
echo \$t;
"
```
then `POST /api/widget/{agent_id}/session` with `{"login_token": "<token>"}`.

### Customer menu — Sales (answered from the knowledge base / product PDFs)

| Button | Underlying question |
|---|---|
| SMPP | "Can you tell me about your SMPP service?" |
| HLR Lookup | "Can you tell me about your HLR Lookup service?" |
| HTTP API | "Can you tell me about your HTTP API service?" |
| Bulk SMS Campaign | "I'd like to send a bulk SMS campaign, around 1000 SMS — can you tell me about that?" |

Expect a real answer sourced from whatever's loaded into that agent's knowledge base (PDF/website), not hardcoded copy. If the KB doesn't have the content, expect the standard no-answer + handoff offer.

### Customer menu — Support (answered from *the visitor's own* SMSC account data)

| Button | Underlying question | Notes |
|---|---|---|
| Message ID not found | "One of my messages wasn't sent — can you check its status?" | Asks for the message id, then looks it up via `get_smsc_own_message_status` — **own account only**, unlike the support-role tool below. Give it a real id, e.g. `66666666-0000-0000-0000-000000000004` (belongs to acme_admin). |
| Delivery report issue | "Can you check my delivery rate — how many of my messages were delivered vs failed recently?" | Uses `get_smsc_delivery_stats`. |
| API/SMPP connection issue | "I'm having trouble connecting via SMPP — can you check my SMPP status and my connection?" | Uses `get_smsc_smpp_status` / `get_smsc_connections`. |
| Billing & balance | "I have a question about my billing — can you check my account balance?" | Uses `get_smsc_balance`. |
| Other | — | No tool applies — skips straight to a human handoff offer. |

Isolation check: authenticate as `acme_admin` and give a message id that belongs to `northwind_admin` (e.g. `66666666-0000-0000-0000-000000000009`) → must come back "couldn't find a message with that id," never that other customer's data.

### Customer menu — Reporting (real numbers, live from the SMSC database)

| Button | Underlying question | Tool |
|---|---|---|
| Delivery Report | delivery rate / sent / delivered / failed | `get_smsc_delivery_stats` |
| Campaign Report | SMS traffic & usage totals for a date range | `get_smsc_traffic` |
| Account/Balance Report | balance + account status | `get_smsc_balance` + `get_smsc_account_status` |
| Custom Report | open-ended — the AI asks what you need first | whichever tool fits the answer |

None of these are pre-authenticated for an anonymous visitor: expect name → email → phone → SMSC username before the first real answer, exactly like typing the same question would.

### Support-staff mode — no menu, just ask

Once identified as `support` (via dashboard login), every message goes straight to the tool-calling assistant. Reuse the **support-role questions** from the "SUPPORT role questions" section above — they work identically whether typed directly or arrived at via this widget path. The customer-only tool (`get_smsc_own_message_status`) is not offered to a support session; it always uses the any-user `get_smsc_message_status` lookup instead.
