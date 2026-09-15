# Hex Tracker — Frontend

A React + TanStack Router single-page app for the Hex Tracker kanban board.
Originally scaffolded with [Lovable](https://lovable.dev) and then converted
into a plain client-side SPA that talks to the FastAPI backend in
[`../backend`](../backend) according to the contract in
[`../openapi.yaml`](../openapi.yaml).

## Development

```sh
npm install
npm run dev
```

## Tests

```sh
npm test
```

Route components (`src/routes/*.tsx`) are rendered through the app's real
router (see `src/test-utils.tsx`) with the API client mocked, so tests
exercise the same `Route.useParams()`/`Route.useRouteContext()` wiring
production uses.

## Built with

- TanStack Router (client-side routing only, no SSR)
- TypeScript
- React
- Tailwind CSS
