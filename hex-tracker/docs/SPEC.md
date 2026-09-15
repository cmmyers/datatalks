# Mini Kanban Board — Product Spec

## Overview

A shareable kanban board: anyone with the link can open it, and everyone on
that link sees the board update live via WebSocket. There are no accounts and
no login — the link itself is the access control ("room").

## Entities

- **Board** — a room. Has an id (used in the URL and the WebSocket path) and
  a name.
- **Column** — fixed set per board: `To Do`, `In Progress`, `Done`. Columns
  are not user-creatable or renamable.
- **Card** — belongs to a column. Has a title (required), an optional
  description, and a position used for ordering within its column.

## User stories & acceptance criteria

1. **Create a board**
   - Creating a board returns an id/link.
   - Visiting that link loads an empty board with the three default columns.

2. **Share a board so others join the same session**
   - Opening the link requires no login.
   - Multiple browser sessions on the same link see identical data.
   - A change made in one session appears in the other without a manual
     refresh (via WebSocket broadcast).

3. **Add a card**
   - A card requires a non-empty title.
   - The new card appears in the target column for all connected clients
     immediately, not just the originating session.

4. **Move a card (between columns or reorder within one)**
   - The move updates the card's column and position and persists it.
   - The move broadcasts to all clients in the room.
   - The new position survives a page reload.

5. **Edit a card's title/description**
   - The edit persists and broadcasts to other connected sessions.

6. **Delete a card**
   - The card is removed from all connected sessions.
   - The deletion persists after reload.

7. **Load current state on join**
   - A client opening the link — even mid-session, after others have already
     made changes — sees the current board state: an initial REST fetch for
     existing state, followed by a WebSocket subscription for live updates
     from that point on.

## Non-goals

- Accounts, login, permissions/roles.
- Presence indicators (who's online, cursors, avatars).
- Conflict resolution beyond last-write-wins.
- Reconnection/offline resilience — a dropped WebSocket connection is
  resolved by reloading the page, not by automatic reconnect logic.
- Custom or renamable columns.
- Activity history / audit log.
- Rate limiting or abuse prevention on board creation.
