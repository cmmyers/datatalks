import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { createBoard } from "../lib/api";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setIsCreating(true);
    setError(null);
    try {
      const board = await createBoard(name.trim() || undefined);
      await navigate({ to: "/boards/$boardId", params: { boardId: board.id } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setIsCreating(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center text-foreground">
      <h1 className="text-3xl font-semibold tracking-tight">Hex Tracker</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        Create a board and share the link — anyone who opens it sees and edits the same board.
      </p>
      <div className="flex w-full max-w-xs flex-col gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleCreate();
          }}
          placeholder="Board name (optional)"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          onClick={handleCreate}
          disabled={isCreating}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {isCreating ? "Creating…" : "Create a board"}
        </button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
