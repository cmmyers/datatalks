import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as api from "../lib/api";
import { renderAtPath } from "../test-utils";
import type { Board } from "../lib/api";

vi.mock("../lib/api");

function makeBoard(overrides: Partial<Board> = {}): Board {
  return {
    id: "board-1",
    name: "Sprint Planning",
    columns: [
      { id: "todo", title: "To Do", cards: [] },
      { id: "in-progress", title: "In Progress", cards: [] },
      { id: "done", title: "Done", cards: [] },
    ],
    ...overrides,
  };
}

describe("board page", () => {
  it("shows a loading state, then the board's columns and cards", async () => {
    const board = makeBoard({
      columns: [
        {
          id: "todo",
          title: "To Do",
          cards: [
            {
              id: "card-1",
              column_id: "todo",
              title: "Write tests",
              description: "",
              tag: "New",
              position: 0,
            },
          ],
        },
        { id: "in-progress", title: "In Progress", cards: [] },
        { id: "done", title: "Done", cards: [] },
      ],
    });
    vi.mocked(api.getBoard).mockResolvedValue(board);

    renderAtPath("/boards/board-1");

    expect(await screen.findByText(/loading board/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Sprint Planning" })).toBeInTheDocument();
    expect(screen.getByText("Write tests")).toBeInTheDocument();
  });

  it("shows a not-found message when the board doesn't exist", async () => {
    vi.mocked(api.getBoard).mockRejectedValue(new Error("No board exists with id 'board-1'"));

    renderAtPath("/boards/board-1");

    expect(await screen.findByText(/no board exists/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /create a new board/i })).toBeInTheDocument();
  });

  it("adds a card to a column", async () => {
    vi.mocked(api.getBoard).mockResolvedValue(makeBoard());
    vi.mocked(api.createCard).mockResolvedValue({
      id: "card-1",
      column_id: "todo",
      title: "Write tests",
      description: "",
      tag: "New",
      position: 0,
    });
    const user = userEvent.setup();

    renderAtPath("/boards/board-1");
    await screen.findByRole("heading", { name: "Sprint Planning" });

    const todoColumn = screen.getByText("To Do").closest("section");
    if (!todoColumn) throw new Error("To Do column not found");
    await user.click(within(todoColumn).getByRole("button", { name: /add card/i }));
    await user.type(within(todoColumn).getByPlaceholderText("Card title"), "Write tests");
    await user.click(within(todoColumn).getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(api.createCard).toHaveBeenCalledWith("board-1", {
        column_id: "todo",
        title: "Write tests",
        description: "",
      }),
    );
  });

  it("edits a card's title and description", async () => {
    const board = makeBoard({
      columns: [
        {
          id: "todo",
          title: "To Do",
          cards: [
            {
              id: "card-1",
              column_id: "todo",
              title: "Old title",
              description: "Old desc",
              tag: "New",
              position: 0,
            },
          ],
        },
        { id: "in-progress", title: "In Progress", cards: [] },
        { id: "done", title: "Done", cards: [] },
      ],
    });
    vi.mocked(api.getBoard).mockResolvedValue(board);
    vi.mocked(api.updateCard).mockResolvedValue({
      id: "card-1",
      column_id: "todo",
      title: "New title",
      description: "New desc",
      tag: "New",
      position: 0,
    });
    const user = userEvent.setup();

    renderAtPath("/boards/board-1");
    await screen.findByText("Old title");

    await user.click(screen.getByRole("button", { name: /edit card/i }));
    const titleInput = screen.getByDisplayValue("Old title");
    await user.clear(titleInput);
    await user.type(titleInput, "New title");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(api.updateCard).toHaveBeenCalledWith("board-1", "card-1", {
        title: "New title",
        description: "Old desc",
      }),
    );
  });

  it("deletes a card", async () => {
    const board = makeBoard({
      columns: [
        {
          id: "todo",
          title: "To Do",
          cards: [
            {
              id: "card-1",
              column_id: "todo",
              title: "Gone soon",
              description: "",
              tag: "New",
              position: 0,
            },
          ],
        },
        { id: "in-progress", title: "In Progress", cards: [] },
        { id: "done", title: "Done", cards: [] },
      ],
    });
    vi.mocked(api.getBoard).mockResolvedValue(board);
    vi.mocked(api.deleteCard).mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderAtPath("/boards/board-1");
    await screen.findByText("Gone soon");

    await user.click(screen.getByRole("button", { name: /delete card/i }));

    await waitFor(() => expect(api.deleteCard).toHaveBeenCalledWith("board-1", "card-1"));
  });

  it("renames the board", async () => {
    vi.mocked(api.getBoard).mockResolvedValue(makeBoard({ name: "Old name" }));
    vi.mocked(api.updateBoard).mockResolvedValue(makeBoard({ name: "New name" }));
    const user = userEvent.setup();

    renderAtPath("/boards/board-1");
    await screen.findByRole("heading", { name: "Old name" });

    await user.click(screen.getByRole("button", { name: /rename board/i }));
    const nameInput = screen.getByDisplayValue("Old name");
    await user.clear(nameInput);
    await user.type(nameInput, "New name{Enter}");

    await waitFor(() =>
      expect(api.updateBoard).toHaveBeenCalledWith("board-1", { name: "New name" }),
    );
  });
});
