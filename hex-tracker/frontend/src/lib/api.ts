const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type ColumnId = "todo" | "in-progress" | "done";

export type Card = {
  id: string;
  column_id: ColumnId;
  title: string;
  description: string;
  tag: string;
  position: number;
};

export type Column = {
  id: ColumnId;
  title: string;
  cards: Card[];
};

export type Board = {
  id: string;
  name: string;
  columns: Column[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body ? String(body.detail) : null;
    throw new Error(detail ?? `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function createBoard(name?: string): Promise<Board> {
  return request<Board>("/boards", { method: "POST", body: JSON.stringify({ name }) });
}

export function getBoard(boardId: string): Promise<Board> {
  return request<Board>(`/boards/${boardId}`);
}

export function updateBoard(boardId: string, input: { name: string }): Promise<Board> {
  return request<Board>(`/boards/${boardId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function createCard(
  boardId: string,
  input: { column_id: ColumnId; title: string; description?: string },
): Promise<Card> {
  return request<Card>(`/boards/${boardId}/cards`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateCard(
  boardId: string,
  cardId: string,
  input: Partial<{
    title: string;
    description: string;
    column_id: ColumnId;
    position: number;
  }>,
): Promise<Card> {
  return request<Card>(`/boards/${boardId}/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteCard(boardId: string, cardId: string): Promise<void> {
  return request<void>(`/boards/${boardId}/cards/${cardId}`, { method: "DELETE" });
}

type BoardUpdatedEvent = { type: "board_updated"; board: Board };

/** Subscribes to a board's live-update room (see docs/WEBSOCKETS.md).
 * `onUpdate` fires with the full board snapshot whenever the board changes,
 * from any session. Returns an unsubscribe function; per docs/SPEC.md's
 * non-goals there's no reconnect logic — a dropped connection stays
 * dropped until the page is reloaded. */
export function subscribeToBoard(boardId: string, onUpdate: (board: Board) => void): () => void {
  const wsUrl = `${API_URL.replace(/^http/, "ws")}/boards/${boardId}/ws`;
  const socket = new WebSocket(wsUrl);

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data as string) as BoardUpdatedEvent;
    if (data.type === "board_updated") {
      onUpdate(data.board);
    }
  };

  return () => socket.close();
}
