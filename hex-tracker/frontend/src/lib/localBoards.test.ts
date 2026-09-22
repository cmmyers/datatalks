import { beforeEach, describe, expect, it } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import { LOCAL_BOARDS_QUERY_KEY, readLocalBoards, rememberLocalBoard } from "./localBoards";

beforeEach(() => {
  localStorage.clear();
});

describe("readLocalBoards", () => {
  it("returns an empty list when nothing is stored", () => {
    expect(readLocalBoards()).toEqual([]);
  });

  it("returns an empty list instead of throwing on corrupted storage", () => {
    localStorage.setItem("hex-tracker:boards", "{not valid json");

    expect(readLocalBoards()).toEqual([]);
  });

  it("ignores entries that aren't {id, name} objects", () => {
    localStorage.setItem(
      "hex-tracker:boards",
      JSON.stringify([{ id: "a", name: "Valid" }, { id: "b" }, "not an object", null]),
    );

    expect(readLocalBoards()).toEqual([{ id: "a", name: "Valid" }]);
  });
});

describe("rememberLocalBoard", () => {
  it("adds a new board to the front of the list", () => {
    const queryClient = new QueryClient();
    rememberLocalBoard(queryClient, { id: "a", name: "First" });
    rememberLocalBoard(queryClient, { id: "b", name: "Second" });

    expect(readLocalBoards()).toEqual([
      { id: "b", name: "Second" },
      { id: "a", name: "First" },
    ]);
  });

  it("updates an existing board's name in place rather than duplicating it", () => {
    const queryClient = new QueryClient();
    rememberLocalBoard(queryClient, { id: "a", name: "First" });
    rememberLocalBoard(queryClient, { id: "b", name: "Second" });
    rememberLocalBoard(queryClient, { id: "a", name: "First (renamed)" });

    expect(readLocalBoards()).toEqual([
      { id: "b", name: "Second" },
      { id: "a", name: "First (renamed)" },
    ]);
  });

  it("writes straight into the query cache so subscribers update immediately", () => {
    const queryClient = new QueryClient();

    rememberLocalBoard(queryClient, { id: "a", name: "First" });

    expect(queryClient.getQueryData(LOCAL_BOARDS_QUERY_KEY)).toEqual([{ id: "a", name: "First" }]);
  });
});
