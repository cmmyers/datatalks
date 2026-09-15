import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { LOCAL_BOARDS_QUERY_KEY, readLocalBoards } from "../lib/localBoards";

export function BoardSidebar() {
  // Not a real network fetch — just a reactive read of localStorage,
  // kept in sync by rememberLocalBoard() writing into this same query key
  // whenever a board is created, opened, or renamed.
  const { data: boards } = useQuery({
    queryKey: LOCAL_BOARDS_QUERY_KEY,
    queryFn: readLocalBoards,
    initialData: readLocalBoards,
    staleTime: Infinity,
  });

  const { boardId: activeBoardId } = useParams({ strict: false });

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-card/40 px-3 py-6">
      <Link
        to="/"
        className="mb-4 block px-2 text-sm font-semibold tracking-tight text-foreground"
      >
        Hex Tracker
      </Link>
      <h2 className="px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Your boards
      </h2>
      {boards.length === 0 ? (
        <p className="px-2 py-2 text-xs text-muted-foreground">
          Boards you create or open will show up here.
        </p>
      ) : (
        <nav className="mt-1 flex flex-col gap-0.5">
          {boards.map((board) => (
            <Link
              key={board.id}
              to="/boards/$boardId"
              params={{ boardId: board.id }}
              aria-current={board.id === activeBoardId ? "page" : undefined}
              className={`truncate rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-accent ${
                board.id === activeBoardId
                  ? "bg-accent font-medium text-foreground"
                  : "text-muted-foreground"
              }`}
            >
              {board.name}
            </Link>
          ))}
        </nav>
      )}
    </aside>
  );
}
