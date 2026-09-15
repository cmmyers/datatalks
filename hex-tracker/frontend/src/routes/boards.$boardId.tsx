import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Plus, X, GripVertical, Pencil, Check } from "lucide-react";

import {
  createCard,
  deleteCard,
  getBoard,
  updateBoard,
  updateCard,
  type ColumnId,
} from "../lib/api";

export const Route = createFileRoute("/boards/$boardId")({
  component: BoardPage,
});

const JEWEL_STYLES: Record<
  ColumnId,
  { header: string; dot: string; badge: string; ring: string }
> = {
  todo: {
    header: "bg-jewel-amethyst-light text-jewel-amethyst",
    dot: "bg-jewel-amethyst",
    badge: "bg-jewel-amethyst-light text-jewel-amethyst",
    ring: "ring-jewel-amethyst/30",
  },
  "in-progress": {
    header: "bg-jewel-sapphire-light text-jewel-sapphire",
    dot: "bg-jewel-sapphire",
    badge: "bg-jewel-sapphire-light text-jewel-sapphire",
    ring: "ring-jewel-sapphire/30",
  },
  done: {
    header: "bg-jewel-emerald-light text-jewel-emerald",
    dot: "bg-jewel-emerald",
    badge: "bg-jewel-emerald-light text-jewel-emerald",
    ring: "ring-jewel-emerald/30",
  },
};

function BoardPage() {
  const { boardId } = Route.useParams();
  const queryClient = useQueryClient();
  const boardQuery = useQuery({
    queryKey: ["board", boardId],
    queryFn: () => getBoard(boardId),
  });

  const [addingToColumn, setAddingToColumn] = useState<ColumnId | null>(null);
  const [newCardTitle, setNewCardTitle] = useState("");
  const [newCardDescription, setNewCardDescription] = useState("");
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const [editCardTitle, setEditCardTitle] = useState("");
  const [editCardDescription, setEditCardDescription] = useState("");
  const dragSource = useRef<{ columnId: ColumnId; cardId: string } | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["board", boardId] });

  const addCardMutation = useMutation({
    mutationFn: (input: { column_id: ColumnId; title: string; description: string }) =>
      createCard(boardId, input),
    onSuccess: invalidate,
  });

  const moveCardMutation = useMutation({
    mutationFn: (input: { cardId: string; column_id: ColumnId }) =>
      updateCard(boardId, input.cardId, { column_id: input.column_id }),
    onSuccess: invalidate,
  });

  const editCardMutation = useMutation({
    mutationFn: (input: { cardId: string; title: string; description: string }) =>
      updateCard(boardId, input.cardId, { title: input.title, description: input.description }),
    onSuccess: invalidate,
  });

  const deleteCardMutation = useMutation({
    mutationFn: (cardId: string) => deleteCard(boardId, cardId),
    onSuccess: invalidate,
  });

  const renameBoardMutation = useMutation({
    mutationFn: (newName: string) => updateBoard(boardId, { name: newName }),
    onSuccess: invalidate,
  });

  const handleDragStart = (
    e: React.DragEvent<HTMLDivElement>,
    columnId: ColumnId,
    cardId: string,
  ) => {
    dragSource.current = { columnId, cardId };
    e.dataTransfer.effectAllowed = "move";
    e.currentTarget.classList.add("opacity-50");
  };

  const handleDragEnd = (e: React.DragEvent<HTMLDivElement>) => {
    e.currentTarget.classList.remove("opacity-50");
    dragSource.current = null;
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (e: React.DragEvent, targetColumnId: ColumnId) => {
    e.preventDefault();
    const source = dragSource.current;
    if (!source || source.columnId === targetColumnId) return;
    moveCardMutation.mutate({ cardId: source.cardId, column_id: targetColumnId });
  };

  const addCard = (columnId: ColumnId) => {
    const title = newCardTitle.trim();
    if (!title) return;
    addCardMutation.mutate({
      column_id: columnId,
      title,
      description: newCardDescription.trim(),
    });
    setNewCardTitle("");
    setNewCardDescription("");
    setAddingToColumn(null);
  };

  const startEditingName = (currentName: string) => {
    setNameDraft(currentName);
    setIsEditingName(true);
  };

  const saveNameEdit = () => {
    const name = nameDraft.trim();
    if (!name) {
      setIsEditingName(false);
      return;
    }
    renameBoardMutation.mutate(name);
    setIsEditingName(false);
  };

  const startEditingCard = (cardId: string, title: string, description: string) => {
    setEditingCardId(cardId);
    setEditCardTitle(title);
    setEditCardDescription(description);
  };

  const saveCardEdit = () => {
    const title = editCardTitle.trim();
    if (!title || !editingCardId) {
      setEditingCardId(null);
      return;
    }
    editCardMutation.mutate({
      cardId: editingCardId,
      title,
      description: editCardDescription.trim(),
    });
    setEditingCardId(null);
  };

  if (boardQuery.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Loading board…
      </div>
    );
  }

  if (boardQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background px-4 text-center">
        <p className="text-sm text-muted-foreground">
          {boardQuery.error instanceof Error ? boardQuery.error.message : "Board not found."}
        </p>
        <Link to="/" className="text-sm font-medium text-primary underline">
          Create a new board
        </Link>
      </div>
    );
  }

  const board = boardQuery.data;

  return (
    <div className="flex min-h-screen flex-col bg-background px-6 py-8 text-foreground">
      <header className="mb-8">
        {isEditingName ? (
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveNameEdit();
                if (e.key === "Escape") setIsEditingName(false);
              }}
              onBlur={saveNameEdit}
              className="rounded-md border border-input bg-background px-2 py-1 text-3xl font-semibold tracking-tight text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        ) : (
          <button
            onClick={() => startEditingName(board.name)}
            className="group flex items-center gap-2 text-left"
            aria-label="Rename board"
          >
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">
              {board.name}
            </h1>
            <Pencil className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        )}
        <p className="mt-1 text-sm text-muted-foreground">
          Drag cards between columns to track progress. Share this page's link to collaborate.
        </p>
      </header>

      <main className="flex flex-1 gap-5 overflow-x-auto pb-4">
        {board.columns.map((column) => {
          const styles = JEWEL_STYLES[column.id];
          return (
            <section
              key={column.id}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, column.id)}
              className="flex min-w-[17rem] max-w-[17rem] flex-1 flex-col rounded-2xl border border-border bg-card/60 p-4 shadow-sm backdrop-blur-sm"
            >
              <div
                className={`mb-4 flex items-center justify-between rounded-xl px-3 py-2 ${styles.header}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
                  <h2 className="text-sm font-semibold">{column.title}</h2>
                </div>
                <span className="text-xs font-medium opacity-80">{column.cards.length}</span>
              </div>

              <div className="flex flex-1 flex-col gap-3">
                {column.cards.map((card) =>
                  editingCardId === card.id ? (
                    <div
                      key={card.id}
                      className="rounded-xl border border-border bg-card p-3 shadow-sm"
                    >
                      <input
                        autoFocus
                        value={editCardTitle}
                        onChange={(e) => setEditCardTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveCardEdit();
                          if (e.key === "Escape") setEditingCardId(null);
                        }}
                        placeholder="Card title"
                        className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                      <textarea
                        value={editCardDescription}
                        onChange={(e) => setEditCardDescription(e.target.value)}
                        placeholder="Description (optional)"
                        rows={2}
                        className="mt-2 w-full resize-none rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                      <div className="mt-2 flex items-center justify-end gap-2">
                        <button
                          onClick={() => setEditingCardId(null)}
                          className="rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={saveCardEdit}
                          disabled={!editCardTitle.trim()}
                          className="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Save
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div
                      key={card.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, column.id, card.id)}
                      onDragEnd={handleDragEnd}
                      className={`group relative cursor-grab rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:shadow-md active:cursor-grabbing ${styles.ring} focus:outline-none focus:ring-2`}
                    >
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <span
                          className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles.badge}`}
                        >
                          {card.tag}
                        </span>
                        <div className="flex items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
                          <button
                            onClick={() =>
                              startEditingCard(card.id, card.title, card.description)
                            }
                            aria-label="Edit card"
                          >
                            <Pencil className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                          </button>
                          <button
                            onClick={() => deleteCardMutation.mutate(card.id)}
                            aria-label="Delete card"
                          >
                            <X className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                          </button>
                        </div>
                      </div>
                      <h3 className="text-sm font-semibold leading-snug text-card-foreground">
                        {card.title}
                      </h3>
                      {card.description && (
                        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                          {card.description}
                        </p>
                      )}
                      <GripVertical className="absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/40" />
                    </div>
                  ),
                )}

                {addingToColumn === column.id ? (
                  <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                    <input
                      autoFocus
                      value={newCardTitle}
                      onChange={(e) => setNewCardTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") addCard(column.id);
                        if (e.key === "Escape") setAddingToColumn(null);
                      }}
                      placeholder="Card title"
                      className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <textarea
                      value={newCardDescription}
                      onChange={(e) => setNewCardDescription(e.target.value)}
                      placeholder="Description (optional)"
                      rows={2}
                      className="mt-2 w-full resize-none rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                    <div className="mt-2 flex items-center justify-end gap-2">
                      <button
                        onClick={() => setAddingToColumn(null)}
                        className="rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => addCard(column.id)}
                        disabled={!newCardTitle.trim()}
                        className="rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingToColumn(column.id)}
                    className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border py-2.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent hover:text-foreground"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add card
                  </button>
                )}
              </div>
            </section>
          );
        })}
      </main>
    </div>
  );
}
