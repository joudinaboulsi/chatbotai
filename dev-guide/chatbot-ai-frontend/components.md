# Shared Components

## Auth

**`AuthContext.tsx`** (`src/context/`) — the app's only React context. `AuthProvider` holds
`user: UserOut | null` and `loading: boolean`, loaded once on mount via `authApi.me()` if an
access token exists. Exposes `login(email, password)` (calls `/auth/login`, stores tokens, then
fetches `/auth/me`) and `logout()` (calls `/auth/logout` best-effort, then clears local tokens
regardless of whether that call succeeds). `useAuth()` throws if called outside the provider.

**`RequireAuth.tsx`** (`src/components/`) — route guard. Shows a loading spinner while the auth
state is resolving, redirects to `/login` (preserving the attempted location in router state) if
there's no user, otherwise renders its children.

## Layout (`src/components/layout/`)

| Component | Purpose |
|---|---|
| `AppLayout.tsx` | The shell: fixed `Sidebar` on desktop (hidden on mobile, toggled via a hamburger button into a slide-over), a topbar with `NotificationBell` and a logout button, and `<Outlet />` for the routed page. |
| `Sidebar.tsx` | Static nav list — currently just Dashboard/AI Agents/Knowledge Base/Conversations/Leads/Settings, each with a `lucide-react` icon, active-state styling via `NavLink`'s render-prop. **Live Agents and Agent Operators are commented out of the nav array** ("hidden from the nav for now (not in use)") — their routes and pages still exist and are reachable by URL, they're just unlinked. |
| `NotificationBell.tsx` | Bell icon with unread-style dropdown. **Real-time**: opens a `WebSocket` to `/api/ws/notifications?token=<access_token>` on mount, prepends incoming notifications to local state, auto-reconnects 3s after any close. A 60-second `setInterval` poll (`notificationsApi.list()`) runs alongside as a fallback in case the socket drops without firing `onclose` (e.g. some proxies) — the only place in this app that isn't purely fetch-on-mount/fetch-on-action. |

## UI primitives (`src/components/ui/`)

| Component | Purpose |
|---|---|
| `Button.tsx` | 4 variants (`primary`/`secondary`/`danger`/`ghost`) via a class-lookup map; otherwise a plain `<button>` passthrough. |
| `Badge.tsx` | Colored status pill — `COLOR_MAP` keyed by every status string used anywhere in the app (agent/conversation/lead/document statuses all share one map, so a value like `active` or `resolved` always renders the same color regardless of which entity it's describing). |
| `Field.tsx` | Labeled form controls: `Input`, `Textarea`, `Select`, and `ColorInput` (a color swatch + hex text input pair, used on the branding tab). |
| `Modal.tsx` | Generic centered dialog with a title, close button, and configurable max-width. |
| `ConfirmDialog.tsx` | `Modal` preset for "are you sure" prompts — title/message/confirm-label, optional `danger` styling, `onConfirm`/`onCancel`. |
| `EmbedCodeModal.tsx` | Shows the widget `<script>` embed snippet after agent creation, with copy-to-clipboard. |
| `RowActionsMenu.tsx` | The "⋯" per-row dropdown used in every list page (Agents/Operators/etc.) — renders via `createPortal` so it isn't clipped by a table's `overflow`, positions itself with `useLayoutEffect`. |
| `Feedback.tsx` | `LoadingSpinner`, `EmptyState`, `ErrorBanner` — the three states every list/detail page renders while data isn't ready. |
| `Toast.tsx` | `ToastProvider` + `useToast()` — app-wide success/error toast notifications, mounted once in `main.tsx`. |
| `Switch.tsx` | Labeled on/off toggle (`label`, optional `description`, `checked`, `onChange`, `disabled`) — a `role="switch"` button styled as a pill. Used on the Settings page for the SMSC integration's "Enabled" flag. |

## Domain components (`src/components/agents/`)

**`AgentBasicForm.tsx`** — the agent name/description/display-name/industry/language-restriction/
remarks/notification-email form, shared verbatim between `AgentCreatePage` and the "Basic" tab of
`AgentDetailPage`. Language restriction is a two-state radio (`'none' | 'specific'`) that reveals a
multi-select of `LANGUAGE_OPTIONS` (from `src/lib/agentOptions.ts`) when set to `specific`.
