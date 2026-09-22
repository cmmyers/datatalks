# WebSocket events

Not representable in `openapi.yaml` (OpenAPI 3.0 has no WebSocket support),
so documented here instead. Implements docs/SPEC.md's "Share a board so
others join the same session" and "Load current state on join" stories.

## Connecting

```
GET /boards/{board_id}/ws
```

Upgrades to a WebSocket. If `board_id` doesn't exist, the server closes the
connection immediately with code `4004`. Otherwise the connection stays open
and receives events until the client disconnects — there's no
reconnect/resume logic on either side (see SPEC.md non-goals); a dropped
connection is resolved by reloading the page, which re-fetches state via
`GET /boards/{board_id}` and opens a fresh socket.

The client sends nothing on this socket; it's receive-only.

## Events

A single event type, sent to every connection on a board's room whenever
that board's state changes (rename, card added/edited/moved/deleted) —
including back to the client whose own request caused the change, so the UI
has one code path for applying updates regardless of origin:

```json
{
  "type": "board_updated",
  "board": { "...": "same shape as the Board schema in openapi.yaml" }
}
```

The event carries the full board snapshot rather than a diff — simplest to
implement correctly, and consistent with the "last-write-wins, no diffing"
approach the non-goals already commit to for REST.
