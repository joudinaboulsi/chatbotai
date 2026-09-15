# Pages & Routing

## Route table (`src/App.tsx`)

`/login` is public. Every other route is nested under a single `<RequireAuth><AppLayout /></RequireAuth>` wrapper — `RequireAuth` (see [`components.md`](./components.md)) redirects to `/login` if there's no authenticated user; `AppLayout` renders the sidebar/topbar shell around whichever page matches.

| Path | Page | Notes |
|---|---|---|
| `/login` | `LoginPage` | Public, no layout. |
| `/dashboard` | `DashboardPage` | Also the target of `/` and any unmatched path. |
| `/agents` | `AgentsPage` | List. |
| `/agents/new` | `AgentCreatePage` | |
| `/agents/:id` | `AgentDetailPage` | |
| `/knowledge-base` | `KnowledgeBasePage` | |
| `/conversations` | `ConversationsPage` | List. |
| `/conversations/:id` | `ConversationDetailPage` | |
| `/leads` | `LeadsPage` | |
| `/live-agents` | `LiveAgentsPage` | |
| `/operators` | `OperatorsPage` | |
| `/settings` | `SettingsPage` | |

There is no explicit 404 page — `path="*"` just redirects to `/dashboard`.

Note: `/live-agents` and `/operators` are still fully routed and functional, but `Sidebar.tsx` no
longer links to them (its nav array carries a comment: "Live Agents / Agent Operators are hidden
from the nav for now (not in use)"). They're reachable only by typing the URL directly.

## Pages

**`LoginPage`** — email/password form, calls `useAuth().login()` (which itself calls `authApi.login` then `authApi.me`), redirects to the page the user was trying to reach (`location.state.from`) or `/dashboard` on success.

**`DashboardPage`** — the only page using `recharts`. On mount, fires `dashboardApi.stats()` and `dashboardApi.charts()` in parallel. Renders 8 `StatCard`s (total/active/resolved conversations, avg response time, new/today/week/month leads) and 4 charts in `ChartCard` wrappers: a line chart (conversations over time), a bar chart (leads over time), and two pie charts (AI vs. human conversations, conversation status breakdown). `DashboardStats` also carries `live_agent_requests_waiting`, but the page doesn't render a card for it. Uses a fixed 5-color categorical palette (`PIE_COLORS`) with a comment noting it's validated against a "dataviz color-formula" and colors are never reassigned per-value, only by fixed slot order.

**`AgentsPage`** — paginated (10/page), searchable (debounced 250ms), status-filterable table of agents. Row actions menu: view/edit, duplicate, activate/deactivate, delete (behind a `ConfirmDialog`).

**`AgentCreatePage`** — a form (`AgentBasicForm`) to create a new agent; on success, also sets the agent's `display_agent_name` via a branding update, fetches the embed code (`agentsApi.embedCode`), and shows it in an `EmbedCodeModal` so the admin can copy the `<script>` snippet for their website.

**`AgentDetailPage`** — 3-tab editor for one agent: **Basic** (reuses `AgentBasicForm`), **Branding** (colors, fonts, widget position/size, welcome/placeholder text, logo/avatar upload via `Field.tsx`'s `ColorInput`, plus a static style preview panel), **Preview & Embed** (an `<iframe>` running the actual production widget against `/widget-preview.html?agentId=<id>`, with a "Reload" button that bumps `previewKey` to force remount after a branding save; alongside it, the embed `<script>` snippet fetched via `agentsApi.embedCode` with copy-to-clipboard).

**`ConversationsPage`** — paginated list of conversations rendered as cards (avatar with initials, visitor name/phone, status badge + colored status dot, message count, last-message-time, last-message preview). Filters: a status tab bar (All/AI Active/Waiting/Human Active/Resolved/Closed, each showing a live count from `status_counts`), a "has lead / no lead" dropdown, and a sort dropdown (newest/oldest/most messages) — all three are sent to `conversationsApi.list`. The free-text search box, by contrast, is **client-side only**: it filters the already-loaded page of results by name/email/phone and isn't sent to the API. Clicking a card navigates to the detail page, passing the current filtered id list via router state (`{ ids }`) so the detail page can offer prev/next navigation without re-querying.

**`ConversationDetailPage`** — full transcript view for one conversation. Reads `ids` from router state to render prev/next buttons across the filtered list from the previous page. Operator actions: send a reply message (only enabled when status is `human_active` or `waiting_for_agent`), assign to self (when `waiting_for_agent`), mark resolved (when `human_active` or `ai_active`), close. No live updates — loads once on mount via `conversationsApi.get(id)`; sending a message re-fetches the whole conversation afterward (not polling or WebSocket-driven, unlike the notification bell).

**`KnowledgeBasePage`** (857 lines — the largest page) — CRUD for knowledge bases (name, description, source type PDF/website, linked agent ids). **Each knowledge base holds at most one source** (one PDF document, or one scraped site) — this is a UI constraint, not exposed as a backend limit: the create/edit modals only ever show a single document/URL slot, delete-then-recreate when you replace it. The "view" modal shows that one document (with status badge, size, processed/uploaded timestamps, re-process/delete) or that one scraped site (status badge, pages processed/discovered, last-scraped time, re-scrape/edit-URL/delete). Scrape jobs are always created with hardcoded params — `mode: 'single_url'`, `max_pages: 20`, `max_depth: 2`, `include_subpages: true`, `exclude_urls: []` — the page has no UI for crawl mode, max pages/depth, subpage inclusion, or an exclude-URL list, even though `knowledgeApi.createScrape` (see [`api-client.md`](./api-client.md)) accepts all of those.

**`LeadsPage`** — status-filterable list of leads (up to 50 shown), with inline status updates (`leadsApi.update`) via a plain `<select>` dropdown per row.

**`LiveAgentsPage`** — list of live-agent handoff requests with "assign to me" (when `waiting`) and "resolve" (when `assigned`/`active`) actions. Not linked from the sidebar (see routing note above) but fully functional.

**`OperatorsPage`** — CRUD for dashboard operator accounts (name/email/password/role, assigned agent ids). `useAuth()` is used only to compare `op.id !== user?.id` — this hides the "Delete" button on the current user's own row so an operator can't delete their own account. There is **no role-based gating** of create/edit in this page's code (any operator who can reach the page can create/edit/delete others). Not linked from the sidebar (see routing note above) but fully functional.

**`SettingsPage`** — two independent sections on one page: **Email/SMTP settings** (host/port/username/password/encryption/from-address/support-email, plus a "send test email" action) and **SMSC integration settings** (base URL, auth scheme, timeout, session-expiry minutes, API key, plus a "test connection" action showing connected/detail).
