# Frontend

Next.js app for personalized literature discovery.

## Local Development

```bash
cd frontend
npm install
npm run dev
```

In this Codex desktop workspace, use the local Node runtime that was downloaded under `.tools/`:

```bash
cd frontend
PATH="../.tools/node/node-v24.14.0-darwin-arm64/bin:$PATH" ../.tools/node/node-v24.14.0-darwin-arm64/bin/npm run dev
```

Main routes:

- `/`: personalized discovery surface with recommendation rows.
- `/onboarding`: preference capture.
- `/work/[id]`: reader view.
- `/profile`: user taste profile.
- `/messages`: reader conversations.
- `/post`: user-submitted literature.

The current UI uses mock data while the backend recommendation and content APIs are being wired.
