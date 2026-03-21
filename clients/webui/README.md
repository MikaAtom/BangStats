# BangStats Web UI

React + TypeScript SPA for the BangStats API.

## Features
- login and register
- dashboard with sync, jobs, recent screenshots, and error summary
- upload scan flow and server-folder scan flow
- scan job detail and cancellation
- error inbox, error detail, correction, revalidate, and rescan actions
- stats overview, song drilldown, milestones, activity, calendar, and insights
- settings and admin tools

## Run
1. Start the API server from the repo root:
   - `uv run bangstats server --host 127.0.0.1 --port 8010`
2. Install frontend dependencies:
   - `cd clients/webui`
   - `npm install`
3. Start the dev server:
   - `npm run dev`

The Vite dev server proxies `/api/*` requests to `http://127.0.0.1:8010`.

Optional override:
- Set `BANGSTATS_API_TARGET` before `npm run dev` to point the proxy to a different API endpoint.
