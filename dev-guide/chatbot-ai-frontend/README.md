# chatbot-ai frontend

React + TypeScript + Vite single-page app — the **operator dashboard** for the chatbot platform.
Not the customer-facing widget (that's a separate vanilla-JS file, see
[`../widget.md`](../widget.md)). This app is what a support agent, sales admin, or platform admin
uses to configure AI agents, review conversations, manage leads, handle live-agent handoffs, and
adjust settings.

## Running it

```bash
npm install
npm run dev        # Vite dev server
npm run build       # tsc -b && vite build
npm run preview     # preview the production build
npm run lint         # oxlint
```

The app expects the backend API under `/api` (see `src/api/client.ts` — `axios.create({ baseURL: '/api' })`), so in dev it relies on Vite's proxy config (`vite.config.ts`) or being served behind the same origin as the FastAPI backend.

## Folder map

| Path | Purpose |
|---|---|
| `src/api/` | `client.ts` (axios instance + JWT auth/refresh interceptors), `resources.ts` (one object per backend resource — `agentsApi`, `conversationsApi`, etc.), `types.ts` (TypeScript mirrors of the backend's Pydantic schemas). |
| `src/context/` | `AuthContext.tsx` — the only React context in the app; holds the logged-in operator and login/logout methods. |
| `src/components/layout/` | Shell chrome: sidebar nav, top bar, notification bell (WebSocket-fed). |
| `src/components/ui/` | Generic, app-agnostic building blocks (Button, Modal, Badge, Toast, form fields, confirm dialog, row-actions menu). |
| `src/components/agents/` | One agent-specific form component shared between the create and edit flows. |
| `src/components/RequireAuth.tsx` | Route guard — redirects to `/login` if not authenticated. |
| `src/lib/agentOptions.ts` | Static option lists (industries, languages) for agent forms. |
| `src/pages/` | One file per route — see [`pages-and-routing.md`](./pages-and-routing.md). |
| `src/App.tsx` | The route table. |
| `src/main.tsx` | Entry point — mounts `App` wrapped in `BrowserRouter`, `AuthProvider`, `ToastProvider`. |

See [`packages.md`](./packages.md) for dependencies, [`api-client.md`](./api-client.md) for the
API layer, [`pages-and-routing.md`](./pages-and-routing.md) for every page, and
[`components.md`](./components.md) for shared components.
