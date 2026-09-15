import type { QueryClient } from "@tanstack/react-query";

export type LocalBoard = { id: string; name: string };

const STORAGE_KEY = "hex-tracker:boards";

export const LOCAL_BOARDS_QUERY_KEY = ["local-boards"] as const;

export function readLocalBoards(): LocalBoard[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (entry): entry is LocalBoard =>
        typeof entry === "object" &&
        entry !== null &&
        typeof (entry as LocalBoard).id === "string" &&
        typeof (entry as LocalBoard).name === "string",
    );
  } catch {
    // localStorage may be unavailable (private browsing, disabled site
    // data) or hold corrupted JSON from a previous version — either way,
    // just remember nothing rather than breaking the page.
    return [];
  }
}

function writeLocalBoards(boards: LocalBoard[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(boards));
  } catch {
    // Nothing useful to do if storage is full or unavailable — the
    // sidebar just won't remember this board.
  }
}

/**
 * Adds a board to the remembered list (most recent first), or updates its
 * stored name if it's already there — covering both a rename and a name
 * that drifted from another session. Also writes straight into the
 * "local-boards" query's cache so every mounted BoardSidebar re-renders
 * immediately, since localStorage itself isn't reactive.
 */
export function rememberLocalBoard(queryClient: QueryClient, board: LocalBoard): void {
  const boards = readLocalBoards();
  const existingIndex = boards.findIndex((b) => b.id === board.id);
  const next =
    existingIndex === -1
      ? [board, ...boards]
      : boards.map((b, i) => (i === existingIndex ? board : b));

  writeLocalBoards(next);
  queryClient.setQueryData(LOCAL_BOARDS_QUERY_KEY, next);
}
