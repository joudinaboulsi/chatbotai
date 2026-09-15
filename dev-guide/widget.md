# The Widget (`chatbot-ai/backend/widget/widget.js`)

The actual customer-facing chat widget — a single self-contained **vanilla JavaScript** file
(1044 lines), no build step, no framework, no external dependencies. It's what an end customer on
the company's website talks to; this is a different surface from the operator dashboard
(`../chatbot-ai-frontend/`, a full React app).

## Loading & bootstrapping

Embedded via a script tag the dashboard generates for each agent (see
`AgentCreatePage`/`EmbedCodeModal` in the frontend, and `../chatbot-ai-backend/api-routes.md` →
`agents.py`'s embed-code endpoint):
```html
<script src=".../widget.js" data-agent-id="..." data-login-token="..." data-api-base-url="..." async></script>
```
- `data-agent-id` (required) — which agent's config/branding/conversation this widget instance is.
- `data-login-token` (optional) — a short-lived token minted by the Laravel dashboard for an
  already-logged-in SMSC user, so the widget can silently identify them (see
  `smsc_service.identify_from_widget_login_token` in the backend) instead of asking for a
  username in chat.
- `data-api-base-url` (optional) — defaults to the script's own origin.

The IIFE finds its own `<script>` tag via `document.currentScript` (falling back to a reverse
scan of all `<script>` tags for one whose `src` contains `widget.js`, for browsers/bundling setups
where `currentScript` isn't reliable), reads its `data-*` attributes, then waits for
`DOMContentLoaded` (or runs immediately if the document is already loaded) before calling
`widget.init()`.

## Rendering: Shadow DOM

`_buildDom()` appends one host `<div>` to `document.body` and calls
`host.attachShadow({ mode: "closed" })` — every widget style and node lives inside a **closed
shadow root**, so the host page's CSS can never leak in or clash with the widget's own styles, and
the host page's JS can't reach into the widget's internals via `host.shadowRoot`. All CSS is
generated as one big string in `_css()` (template-interpolated from the agent's branding colors)
and injected via a single `<style>` element — no external stylesheet, no CSS-in-JS library.

## Talking to the backend

- `apiUrl(path)` → `API_BASE + "/api/widget" + path`.
- `apiRequest(path, options)` — thin `fetch()` wrapper; throws with the backend's `detail` message
  (or a generic "Request failed (status)") on a non-OK response; returns `null` on `204`.
- `streamRequest(path, payload, onToken)` — POSTs and reads the response body as a **Server-Sent
  Events** stream by hand (no `EventSource`, since that only supports GET): parses `event:`/`data:`
  frames out of the raw byte stream, calling `onToken(text)` for each `event: token`, resolving
  with the `event: done` payload, and throwing on `event: error` or if the stream ends without a
  `done` event. Used only by `_sendCurrentInput` for the live-typing effect; every other
  request/response in the widget is the plain non-streaming `apiRequest`.

Every one of these hits routes under `/api/widget/...` — see
[`chatbot-ai-backend/api-routes.md`](./chatbot-ai-backend/api-routes.md) → `widget.py` for the
server side of each call below.

## Helper functions (module scope)

| Function | Purpose |
|---|---|
| `el(tag, attrs, children)` | The only DOM-construction helper in the file — no JSX, no templates. `attrs.style` gets `Object.assign`'d onto `node.style`; any `attrs.onKey` where `Key` starts lowercase-`on` and is a function gets wired via `addEventListener`; everything else is `setAttribute`. Children: strings become text nodes, falsy values are skipped. |
| `escapeHtml(str)` | Escapes via a scratch `<div>`'s `textContent`→`innerHTML` round-trip. Used anywhere widget code builds an HTML string by hand (the chart SVG) instead of using `el()`. |
| `hexToRgba(hex, alpha)` | Hex color (3 or 6 digit) → `rgba(...)` string, for translucent shadows/rings derived from the agent's brand colors. |
| `_qrIconKey(value)` | Maps a quick-reply/report-action option's opaque routing `value` (e.g. `"menu_sales"`, `"support_cat_billing"`, `"human_reason_..."`) to one of ~19 icon keys by keyword match, so every button gets an on-topic icon without the backend having to carry icon choices in `message_metadata`. Falls back to a generic chat-bubble icon. |
| `_qrIconSvg(value)` | Looks up `_qrIconKey(value)` in the module-level `_QR_ICONS` map (a small hand-drawn, stroke-based, `currentColor` icon set — cart/support/chart/user/plug/lock/shield/etc., no icon library dependency) and wraps the matched markup in an outer `<svg>` shell. |

## `ChatWidget` — state & lifecycle

Constructor just initializes instance fields (`config` — the fetched branding/config object,
`sessionToken`, `conversationId`, `conversationStatus`, `isOpen`, `hasOpenedOnce` — flips true on
first open and permanently hides the launcher's attention-grabbing pulse ring, `unreadCount`,
`pollTimer`, `lastMessageId`, `renderedMessageIds` — a dedup map so a message never renders twice,
`lastRenderedSender` — used to decide whether to draw an avatar or a blank spacer, since
consecutive same-sender messages share one avatar slot).

| Method | Purpose |
|---|---|
| `init()` | Fetches `/config/{agentId}` (branding colors, fonts, widget size/position, company/agent name, logo/avatar URLs); on failure, logs and gives up silently (no widget renders at all) — on success, calls `_buildDom()`. |
| `_buildDom()` | Builds the shadow root, launcher button, and (initially hidden) panel; computes panel width from `widget_size` (`compact`/`standard`/`large` → 340/380/420px). |
| `_launcherIcon()` / `_closeIcon()` / `_buildHeader()` / `_buildInputArea()` / `_buildAvatarNode()` | DOM-construction helpers for specific pieces of chrome. `_buildAvatarNode` falls back to the agent name's first letter in a colored circle if no avatar/logo URL is configured. |
| `_resolveMediaUrl(url)` | Passes through absolute URLs; prefixes relative ones with `API_BASE`. |
| `_css(panelWidth, position)` | Returns the entire widget stylesheet as one string, interpolating the agent's branding config. Includes a `prefers-reduced-motion` block that disables every animation/transition. |
| `_toggle()` | Open/close the panel. On first-ever open, lazily calls `_ensureSession()` if no conversation exists yet. Switches polling cadence: fast (`POLL_INTERVAL_MS` = 4s) while open, slow (`BACKGROUND_POLL_INTERVAL_MS` = 20s) while closed but a session exists, stopped entirely if there's no session at all. |
| `_ensureSession()` | `POST /{agentId}/session` with `{ session_token, login_token }` — creates or resumes a conversation, renders whatever messages come back (the greeting, typically). |

## Sending a message

`_sendCurrentInput()` is the main send path: echoes the visitor's text immediately (a synthetic
local message with id `"local-" + Date.now()`, deduped later by the real server id), shows a
typing indicator, then tries `streamRequest` first for a live-typing effect via
`_openLiveBubble()`/`_appendLiveToken()` (an empty AI bubble that grows token-by-token). If
streaming fails for any reason (buffering proxy, old browser, endpoint down), it discards the
partial live bubble and falls back to the plain non-streaming `POST /{agentId}/message` — the
visitor's message is never lost to a transport failure. Either way, once the real response
arrives, `_discardLiveBubble()` removes the streamed preview and the server's actual stored
message(s) are rendered instead (so ids/timestamps/quick-replies are correct — the streamed text
was only ever a preview).

`_sendQuickReply(option, buttonsWrap)` is the button-click equivalent: disables the button row for
the duration of the request only (re-enabled after, since a quick-reply isn't always a final
answer — e.g. the backend might still need the visitor's name/email/phone and will just re-ask,
letting them click the same button again once done), posts `{ message: option.label, quick_reply:
option.value }`.

## Rendering a message — `_renderMessage(message)`

The dispatch point for every message the widget shows, whether from `_ensureSession`,
`_sendCurrentInput`, `_sendQuickReply`, `_respondHandoff`, or `_poll`. Dedupes by `message.id`
against `renderedMessageIds`. Builds the basic bubble (sender-styled, with a timestamp if
`created_at` is present), then inspects `message.message_metadata` for a set of optional,
independent payloads. Everything below the bubble renders in a fixed top-to-bottom order — handoff
buttons, report header, stat tiles, delivery-rate progress, trend chart, peak/low-activity rows,
breakdown rows, report drill-down actions, then generic quick-replies — so a report always reads
data-first, with the ever-present Sales/Support/Live-Agent-style follow-up options last:

1. **`metadata.type === "handoff_offer"`** → renders a "Yes, connect me" / "Continue with AI"
   button pair wired to `_respondHandoff(true|false)`.
2. **`metadata.header`** (`{ title?, period? }`) → a 📊-prefixed report title and/or a period line.
3. **`Array.isArray(metadata.stats)`** → a responsive grid of stat tiles (value + label);
   `stat.tone` (`"positive"`/`"negative"`/`"neutral"`) colors the tile's left border.
4. **`metadata.progress`** (`{ percent, sub? }`) → a labeled "Delivered" progress bar (percent
   clamped to 0–100, colored red below 90%), with an optional row of secondary percentages
   (`sub`) underneath.
5. **`metadata.chart`** → passed to `_buildChartNode(chart)` (see below); if it returns a node,
   it's appended.
6. **`metadata.peak` / `metadata.low`**, then **`metadata.breakdown.rows`** (with
   `metadata.breakdown.title`) → each passed through the shared
   `_appendReportRows(col, title, rows)` helper, rendering a titled ("🔥 Peak Traffic" /
   "📉 Low Activity" / breakdown-specific) list of compact rows (`{date, primary, secondary}`).
   All of these figures come from real tool-call data computed server-side
   (`smsc_ai_service._build_report_extras`/`_build_breakdown_rows`), never from the model's own
   text.
7. **`Array.isArray(metadata.report_actions)`**, then **`Array.isArray(metadata.options)`** —
   both render through the shared `_buildQuickRepliesNode(options)` helper: a responsive grid of
   icon cards (`.quick-replies`/`.qr-card`, not a plain vertical button list), each wired to
   `_sendQuickReply(option, wrap)` with an icon picked by `_qrIconKey`/`_qrIconSvg` from the
   option's routing `value`.

If the panel is closed and the message isn't from the visitor and isn't a local echo, it also
bumps the unread badge (`_addUnread()`).

## Chart rendering — `_buildChartNode(chart)`

One of several report-metadata visual blocks `_renderMessage` can append (see above) — draws a
small inline line chart. The chart data contract (matches `smsc_ai_service._build_chart` on the Python side, documented in
[`chatbot-ai-backend/services.md`](./chatbot-ai-backend/services.md)):
```ts
{ type: "line", title: string, labels: string[], series: { name: string; values: number[] }[] }
```
Only `type === "line"` is handled — anything else (or fewer than 2 labels, or no series) returns
`null` and nothing renders, so a malformed/future payload fails closed instead of drawing garbage.

Implementation: hand-built **inline SVG**, no charting library. Computes `x`/`y` pixel positions
from a fixed `300×150` viewBox, draws one `<polyline>` + a `<circle>` per data point per series
(cycling through a 4-color palette), labels only the first and last x-axis tick (to avoid clutter
on a narrow panel), and appends a color-dot legend below the chart as a separate `<div>`. Built as
one HTML string (via `escapeHtml` for any text) and set via `.innerHTML` on a wrapper `el("div",
{ class: "chat-chart" })`, rather than using `document.createElementNS` for real SVG DOM nodes —
simpler given `el()` only supports HTML namespace elements.

**Why no chart library**: this is a single-file, no-build-step, no-framework widget — pulling in
Chart.js/Recharts/etc. (and a bundler to use them sensibly) would be a much bigger change than the
two-series line chart it actually needs to draw. The operator dashboard (a real React app) does
use a charting library (`recharts`) for its own, unrelated charts — see
[`chatbot-ai-frontend/packages.md`](./chatbot-ai-frontend/packages.md).

## Handoff & polling

- `_respondHandoff(accepted)` — `POST /{agentId}/handoff` with `{ accepted }`, renders whatever
  messages come back.
- `_startPolling(intervalMs)` / `_stopPolling()` / `_poll()` — `_poll` does nothing if there's no
  session yet; otherwise `GET /{agentId}/messages?session_token=...&after=<lastMessageId>`. Unlike
  a send's response (which never echoes the visitor's own message back), this endpoint returns
  full history after a cursor with no such exclusion — so for any `sender_type === "visitor"`
  message in the batch, `_poll` just advances `lastMessageId` past it without rendering (it's
  already on screen via the local echo from `_sendCurrentInput`/`_sendQuickReply`), avoiding a
  duplicate render under the message's real server id. Every other message renders normally.
  Polling failures are swallowed silently — a transient network blip shouldn't surface an error to
  the visitor mid-conversation. (Note: unlike the dashboard's `NotificationBell`, the widget has no
  WebSocket path at all — polling is its only mechanism for picking up messages sent from the
  operator side.)

## Misc

- `_formatTime(iso)` — locale time string, or `""` on an unparseable date (never throws).
- `_showTyping()` / `_removeTyping()` — the three-dot typing indicator row.
- `_renderError(text)` — a centered red banner appended to the message list (not a toast/alert).
- `_addUnread()` / `_clearUnread()` — the badge on the launcher button.
- `IS_RTL` is detected once from `navigator.language` and applied as `dir="rtl"` on the widget
  root — the widget bundles its own `STRINGS` (English/Arabic) for the handful of static UI
  labels (open/close chat, send, online now); AI-generated message content's language is decided
  server-side, not by this file.
