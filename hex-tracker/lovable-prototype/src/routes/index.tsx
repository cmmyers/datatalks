import { createFileRoute } from "@tanstack/react-router";
import { useState, useRef } from "react";
import { Plus, X, GripVertical, MoreHorizontal } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Kanban Board" },
      { name: "description", content: "A simple drag-and-drop kanban board with a jewel-tone palette." },
      { property: "og:title", content: "Kanban Board" },
      { property: "og:description", content: "A simple drag-and-drop kanban board with a jewel-tone palette." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type Card = {
  id: string;
  title: string;
  description: string;
  tag: string;
};

type ColumnConfig = {
  id: string;
  title: string;
  jewel: "emerald" | "sapphire" | "amethyst" | "topaz";
};

const COLUMNS: ColumnConfig[] = [
  { id: "todo", title: "To Do", jewel: "amethyst" },
  { id: "in-progress", title: "In Progress", jewel: "sapphire" },
  { id: "done", title: "Done", jewel: "emerald" },
];

const INITIAL_CARDS: Record<string, Card[]> = {
  todo: [
    { id: "c1", title: "Research competitors", description: "Gather feature ideas from the top 5 apps in our space.", tag: "Strategy" },
    { id: "c2", title: "Draft PRD", description: "Outline core user flows and acceptance criteria.", tag: "Product" },
  ],
  "in-progress": [
    { id: "c3", title: "Design system", description: "Set up tokens, typography, and component variants.", tag: "Design" },
  ],
  done: [
    { id: "c5", title: "Project kickoff", description: "Team alignment and milestone planning complete.", tag: "Milestone" },
  ],
};

const JEWEL_STYLES: Record<
  ColumnConfig["jewel"],
  { header: string; dot: string; badge: string; ring: string }
> = {
  emerald: {
    header: "bg-jewel-emerald-light text-jewel-emerald",
    dot: "bg-jewel-emerald",
    badge: "bg-jewel-emerald-light text-jewel-emerald",
    ring: "ring-jewel-emerald/30",
  },
  sapphire: {
    header: "bg-jewel-sapphire-light text-jewel-sapphire",
    dot: "bg-jewel-sapphire",
    badge: "bg-jewel-sapphire-light text-jewel-sapphire",
    ring: "ring-jewel-sapphire/30",
  },
  amethyst: {
    header: "bg-jewel-amethyst-light text-jewel-amethyst",
    dot: "bg-jewel-amethyst",
    badge: "bg-jewel-amethyst-light text-jewel-amethyst",
    ring: "ring-jewel-amethyst/30",
  },
  topaz: {
    header: "bg-jewel-topaz-light text-jewel-topaz",
    dot: "bg-jewel-topaz",
    badge: "bg-jewel-topaz-light text-jewel-topaz",
    ring: "ring-jewel-topaz/30",
  },
};

function Index() {
  const [cardsByColumn, setCardsByColumn] = useState<Record<string, Card[]>>(INITIAL_CARDS);
  const [addingToColumn, setAddingToColumn] = useState<string | null>(null);
  const [newCardTitle, setNewCardTitle] = useState("");
  const [newCardDescription, setNewCardDescription] = useState("");
  const dragSource = useRef<{ columnId: string; index: number } | null>(null);

  const handleDragStart = (
    e: React.DragEvent<HTMLDivElement>,
    columnId: string,
    index: number
  ) => {
    dragSource.current = { columnId, index };
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

  const handleDrop = (e: React.DragEvent, targetColumnId: string) => {
    e.preventDefault();
    if (!dragSource.current) return;

    const { columnId: sourceColumnId, index: sourceIndex } = dragSource.current;
    if (sourceColumnId === targetColumnId) return;

    setCardsByColumn((prev) => {
      const sourceCards = [...(prev[sourceColumnId] ?? [])];
      const targetCards = [...(prev[targetColumnId] ?? [])];
      const moved = sourceCards.splice(sourceIndex, 1)[0];
      if (!moved) return prev;
      targetCards.push(moved);
      return { ...prev, [sourceColumnId]: sourceCards, [targetColumnId]: targetCards };
    });
  };

  const addCard = (columnId: string) => {
    const title = newCardTitle.trim();
    if (!title) return;
    const card: Card = {
      id: `c-${Date.now()}`,
      title,
      description: newCardDescription.trim(),
      tag: "New",
    };
    setCardsByColumn((prev) => ({
      ...prev,
      [columnId]: [...(prev[columnId] ?? []), card],
    }));
    setNewCardTitle("");
    setNewCardDescription("");
    setAddingToColumn(null);
  };

  const deleteCard = (columnId: string, cardId: string) => {
    setCardsByColumn((prev) => ({
      ...prev,
      [columnId]: (prev[columnId] ?? []).filter((c) => c.id !== cardId),
    }));
  };

  return (
    <div className="flex min-h-screen flex-col bg-background px-6 py-8 text-foreground">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Project Board
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Drag cards between columns to track progress.
        </p>
      </header>

      <main className="flex flex-1 gap-5 overflow-x-auto pb-4">
        {COLUMNS.map((column) => {
          const styles = JEWEL_STYLES[column.jewel];
          const cards = cardsByColumn[column.id] ?? [];
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
                <span className="text-xs font-medium opacity-80">{cards.length}</span>
              </div>

              <div className="flex flex-1 flex-col gap-3">
                {cards.map((card, index) => (
                  <div
                    key={card.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, column.id, index)}
                    onDragEnd={handleDragEnd}
                    className={`group relative cursor-grab rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:shadow-md active:cursor-grabbing ${styles.ring} focus:outline-none focus:ring-2`}
                  >
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <span
                        className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${styles.badge}`}
                      >
                        {card.tag}
                      </span>
                      <button
                        onClick={() => deleteCard(column.id, card.id)}
                        className="opacity-0 transition-opacity group-hover:opacity-100"
                        aria-label="Delete card"
                      >
                        <X className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                      </button>
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
                ))}

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
