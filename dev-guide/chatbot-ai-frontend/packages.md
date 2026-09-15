# Packages

From `chatbot-ai/frontend/package.json`.

## Dependencies (runtime)

| Package | Version | Used for |
|---|---|---|
| `react` / `react-dom` | ^19.2.8 | UI framework. |
| `react-router-dom` | ^7.18.3 | Client-side routing — `<Routes>`/`<Route>` table in `App.tsx`, `useNavigate`/`useParams`/`useLocation` throughout pages. |
| `axios` | ^1.20.0 | HTTP client — the single `apiClient` instance in `src/api/client.ts`, with request/response interceptors for JWT auth and silent token refresh. |
| `lucide-react` | ^1.41.0 | Icon set — used throughout (`Bell`, `Plus`, `ChevronLeft`, dashboard stat-card icons, sidebar nav icons, etc.). |
| `recharts` | ^3.10.1 | Charting library — used exclusively in `src/pages/DashboardPage.tsx` for the 4 dashboard charts (line chart for conversations over time, bar chart for leads over time, two pie charts for AI-vs-human and status breakdown). Not used anywhere else in this app — the customer-facing widget has its own from-scratch inline-SVG chart renderer instead (see `../widget.md`), since pulling recharts/React into that single-file vanilla-JS script wasn't worth it for two chart types. |

## devDependencies

| Package | Version | Used for |
|---|---|---|
| `typescript` | ~6.0.2 | Type checking; `npm run build` runs `tsc -b` before `vite build`. |
| `vite` | ^8.2.2 | Dev server + bundler. |
| `@vitejs/plugin-react` | ^6.1.0 | Vite's React plugin (JSX transform, fast refresh). |
| `@tailwindcss/vite` + `tailwindcss` | ^4.3.3 | Utility-first CSS — every component uses Tailwind classes directly, no separate CSS files beyond `index.css`. |
| `oxlint` | ^1.79.0 | Linter (`npm run lint`) — a Rust-based ESLint alternative. |
| `@types/node`, `@types/react`, `@types/react-dom` | — | TypeScript type definitions. |

No test runner (no Jest/Vitest/Playwright in `package.json`) — this app currently has no automated
test suite.
