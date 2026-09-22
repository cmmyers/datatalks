import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
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

function sidebarNav() {
  const heading = screen.getByText("Your boards");
  const sidebar = heading.closest("aside");
  if (!sidebar) throw new Error("Sidebar not found");
  return sidebar;
}

beforeEach(() => {
  localStorage.clear();
});

describe("BoardSidebar", () => {
  it("shows an empty state when no boards have been created or opened", async () => {
    vi.mocked(api.getBoard).mockResolvedValue({
      id: "board-1",
      name: "Doesn't matter",
      columns: EMPTY_COLUMNS,
    });

    renderAtPath("/");

    expect(await screen.findByText("Your boards")).toBeInTheDocument();
    expect(within(sidebarNav()).getByText(/will show up here/i)).toBeInTheDocument();
  });

  it("lists a board once it's opened, marked as the active one", async () => {
    vi.mocked(api.getBoard).mockResolvedValue({
      id: "board-1",
      name: "Sprint Planning",
      columns: EMPTY_COLUMNS,
    });

    renderAtPath("/boards/board-1");
    await screen.findByText("Your boards");

    const link = await within(sidebarNav()).findByRole("link", { name: "Sprint Planning" });
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("adds a newly created board to the sidebar right away", async () => {
    vi.mocked(api.createBoard).mockResolvedValue({
      id: "board-2",
      name: "Q3 Roadmap",
      columns: EMPTY_COLUMNS,
    });
    vi.mocked(api.getBoard).mockResolvedValue({
      id: "board-2",
      name: "Q3 Roadmap",
      columns: EMPTY_COLUMNS,
    });
    const user = userEvent.setup();

    renderAtPath("/");
    await user.type(await screen.findByPlaceholderText(/board name/i), "Q3 Roadmap");
    await user.click(screen.getByRole("button", { name: /create a board/i }));

    expect(
      await within(sidebarNav()).findByRole("link", { name: "Q3 Roadmap" }),
    ).toBeInTheDocument();
  });

  it("does not list a board that was never opened in this browser", async () => {
    vi.mocked(api.getBoard).mockResolvedValue({
      id: "board-1",
      name: "Doesn't matter",
      columns: EMPTY_COLUMNS,
    });

    renderAtPath("/");
    await screen.findByText("Your boards");

    expect(
      within(sidebarNav()).queryByRole("link", { name: "Doesn't matter" }),
    ).not.toBeInTheDocument();
  });
});
