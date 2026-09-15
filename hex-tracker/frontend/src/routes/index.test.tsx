import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as api from "../lib/api";
import { renderAtPath } from "../test-utils";
import type { Board } from "../lib/api";

vi.mock("../lib/api");

const EMPTY_COLUMNS: Board["columns"] = [
  { id: "todo", title: "To Do", cards: [] },
  { id: "in-progress", title: "In Progress", cards: [] },
  { id: "done", title: "Done", cards: [] },
];

beforeEach(() => {
  // BoardPage fetches on mount once navigation lands, even in tests that
  // only assert on the landing page — give it a default so that isn't an
  // unhandled rejection.
  vi.mocked(api.getBoard).mockResolvedValue({
    id: "board-1",
    name: "New board",
    columns: EMPTY_COLUMNS,
  });
});

describe("landing page", () => {
  it("creates a board with the entered name and navigates to it", async () => {
    vi.mocked(api.createBoard).mockResolvedValue({
      id: "board-1",
      name: "Sprint Planning",
      columns: EMPTY_COLUMNS,
    });
    const user = userEvent.setup();

    const { router } = renderAtPath("/");
    await user.type(await screen.findByPlaceholderText(/board name/i), "Sprint Planning");
    await user.click(screen.getByRole("button", { name: /create a board/i }));

    await waitFor(() => expect(api.createBoard).toHaveBeenCalledWith("Sprint Planning"));
    await waitFor(() => expect(router.state.location.pathname).toBe("/boards/board-1"));
  });

  it("creates an unnamed board when the name field is left blank", async () => {
    vi.mocked(api.createBoard).mockResolvedValue({
      id: "board-2",
      name: "Untitled board",
      columns: EMPTY_COLUMNS,
    });
    const user = userEvent.setup();

    renderAtPath("/");
    await user.click(await screen.findByRole("button", { name: /create a board/i }));

    await waitFor(() => expect(api.createBoard).toHaveBeenCalledWith(undefined));
  });

  it("shows an error message if board creation fails", async () => {
    vi.mocked(api.createBoard).mockRejectedValue(new Error("Request failed with status 500"));
    const user = userEvent.setup();

    renderAtPath("/");
    await user.click(await screen.findByRole("button", { name: /create a board/i }));

    expect(await screen.findByText(/request failed with status 500/i)).toBeInTheDocument();
  });
});
