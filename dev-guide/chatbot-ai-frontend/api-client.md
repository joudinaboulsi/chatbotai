# API Layer

## `src/api/client.ts` — the HTTP client

- `apiClient = axios.create({ baseURL: '/api' })` — the one axios instance every API call goes
  through.
- **Token storage**: `getAccessToken()`/`getRefreshToken()`/`setTokens()`/`clearTokens()` read and
  write two `localStorage` keys (`access_token`, `refresh_token`).
- **Request interceptor**: attaches `Authorization: Bearer <access_token>` to every outgoing
  request if a token is present.
- **Response interceptor**: on a `401` (and only once per request, guarded by an `_retry` flag),
  calls `POST /api/auth/refresh` with the refresh token, stores the new tokens, and retries the
  original request. Concurrent 401s share a single in-flight refresh call (`refreshPromise`) so a
  burst of requests doesn't fire multiple refreshes. If refresh fails, tokens are cleared and the
  browser is redirected to `/login`.
- `apiErrorMessage(error)` — helper used throughout the app to turn an axios error into a
  user-facing string: prefers the backend's `{ detail: string }` error body, falls back to
  `error.message`, falls back to a generic "Something went wrong."

## `src/api/resources.ts` — one object per backend resource

Every export is a plain object of functions, each a thin wrapper around `apiClient.<verb>()`. No
class, no abstraction beyond this — one function per endpoint.

| Export | Backend resource | Methods |
|---|---|---|
| `authApi` | Auth | `login(email, password)`, `me()`, `logout(refresh_token)` |
| `agentsApi` | AI Agents | `list`, `get`, `create`, `update`, `remove`, `duplicate`, `activate`, `deactivate`, `embedCode`, `getBranding`, `updateBranding`, `uploadLogo`, `uploadAvatar`, `deleteLogo` |
| `knowledgeApi` | Knowledge bases (PDF/website sources) | `list`, `create`, `get`, `update`, `remove`, `uploadPdf`, `listDocuments`, `reprocessDocument`, `deleteDocument`, `createScrape`, `listScrapedSites`, `rescrape`, `deleteScrapedSite` |
| `conversationsApi` | Conversations | `list`, `get`, `sendMessage`, `resolve`, `close`, `assign` |
| `leadsApi` | Leads | `list`, `get`, `update` |
| `liveAgentsApi` | Live-agent handoff requests | `list`, `assign`, `resolve` |
| `operatorsApi` | Dashboard operator accounts | `list`, `create`, `update`, `remove` |
| `notificationsApi` | In-app notifications | `list`, `markRead`, `markAllRead` |
| `settingsApi` | Email/SMTP settings | `getEmail`, `updateEmail`, `testEmail` |
| `smscSettingsApi` | SMSC integration settings | `get`, `update`, `test` |
| `dashboardApi` | Dashboard stats/charts | `stats(agent_id?)`, `charts(agent_id?, days=30)` |
| `auditApi` | Audit log | `list` |

File uploads (`uploadPdf`, `uploadLogo`, `uploadAvatar`) build a `FormData` and post it directly —
axios sets the multipart content-type automatically.

## `src/api/types.ts` — data shapes

TypeScript mirrors of the backend's Pydantic response schemas. All string-literal unions
(`UserRole`, `ConversationStatus`, `LeadStatus`, `NotificationType`, etc.) match the Python enums
in `chatbot-ai/backend/app/models/enums.py` exactly — see
[`../chatbot-ai-backend/models.md`](../chatbot-ai-backend/models.md) for the source of truth if
these ever drift.

Key interfaces: `UserOut` (the logged-in operator), `Agent`, `Branding`, `KnowledgeBase` /
`KnowledgeDocument` / `ScrapedSite`, `ConversationListItem` / `ConversationDetail` / `Message`,
`Lead`, `LiveAgentRequest`, `Operator`, `NotificationOut`, `EmailSettings`, `SMSCSettings`,
`DashboardStats` / `DashboardCharts` (with `DailyCount`/`StatusCount` as the chart-data shapes),
`AuditLogEntry`, and the generic `Paginated<T>` wrapper (`{ items, total, page, page_size }`) used
by every list endpoint.
