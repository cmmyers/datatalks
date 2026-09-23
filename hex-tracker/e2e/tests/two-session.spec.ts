import { test, expect, type Page, type Locator } from "@playwright/test";

/** Creates a board via the home page UI and returns its URL — the same
 * path a real user takes, so this also exercises POST /boards end to end
 * against the container's Postgres. */
async function createBoard(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByPlaceholder("Board name (optional)").fill(name);
  await page.getByRole("button", { name: "Create a board" }).click();
  await page.waitForURL(/\/boards\//);
  return page.url();
}

async function addCard(page: Page, columnTitle: string, cardTitle: string): Promise<void> {
  const column = columnSection(page, columnTitle);
  await column.getByRole("button", { name: "Add card" }).click();
  await column.getByPlaceholder("Card title").fill(cardTitle);
  await column.getByRole("button", { name: "Add" }).click();
}

function columnSection(page: Page, title: string): Locator {
  return page.locator("section").filter({ has: page.getByRole("heading", { name: title }) });
}

/** Navigates to a board and waits until its live-update socket is actually
 * open, not just until the page has loaded. `goto()` resolving only means
 * the HTML/JS arrived — React still has to mount and run the effect that
 * calls subscribeToBoard() (see routes/boards.$boardId.tsx). Without this,
 * a test can send the interviewer's change before the candidate's socket
 * exists, and the broadcast — sent once, never replayed — is simply
 * missed, exactly as the real client behaves per docs/SPEC.md's no-reconnect
 * non-goal. That's a race in the test, not in the app. */
async function gotoAndAwaitLiveConnection(page: Page, url: string): Promise<void> {
  const socket = page.waitForEvent("websocket", (ws) => ws.url().includes("/ws"));
  await page.goto(url);
  await socket;
}

test.describe("live updates across sessions (docs/SPEC.md: 'Share a board so others join the same session')", () => {
  test("a card added in one session appears live in another, with no reload", async ({
    browser,
  }) => {
    const interviewer = await browser.newContext();
    const interviewerPage = await interviewer.newPage();
    const boardUrl = await createBoard(interviewerPage, "Two Session Test");

    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    await gotoAndAwaitLiveConnection(candidatePage, boardUrl);

    await addCard(interviewerPage, "To Do", "Shared card");

    await expect(candidatePage.getByText("Shared card")).toBeVisible();

    await interviewer.close();
    await candidate.close();
  });

  test("moving a card broadcasts live and survives a reload", async ({ browser }) => {
    const interviewer = await browser.newContext();
    const interviewerPage = await interviewer.newPage();
    const boardUrl = await createBoard(interviewerPage, "Move Test");
    await addCard(interviewerPage, "To Do", "Movable card");

    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    await gotoAndAwaitLiveConnection(candidatePage, boardUrl);

    const card = interviewerPage.locator('[draggable="true"]', { hasText: "Movable card" });
    await card.dragTo(columnSection(interviewerPage, "Done"));

    await expect(columnSection(candidatePage, "Done").getByText("Movable card")).toBeVisible();

    await candidatePage.reload();
    await expect(columnSection(candidatePage, "Done").getByText("Movable card")).toBeVisible();

    await interviewer.close();
    await candidate.close();
  });

  test("editing a card's title broadcasts live", async ({ browser }) => {
    const interviewer = await browser.newContext();
    const interviewerPage = await interviewer.newPage();
    const boardUrl = await createBoard(interviewerPage, "Edit Test");
    await addCard(interviewerPage, "To Do", "Original title");

    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    await gotoAndAwaitLiveConnection(candidatePage, boardUrl);

    await interviewerPage.getByRole("button", { name: "Edit card" }).click();
    const titleInput = interviewerPage.getByPlaceholder("Card title");
    await titleInput.fill("Edited title");
    await interviewerPage.getByRole("button", { name: "Save" }).click();

    await expect(candidatePage.getByText("Edited title")).toBeVisible();
    await expect(candidatePage.getByText("Original title")).not.toBeVisible();

    await interviewer.close();
    await candidate.close();
  });

  test("deleting a card broadcasts live and persists after reload", async ({ browser }) => {
    const interviewer = await browser.newContext();
    const interviewerPage = await interviewer.newPage();
    const boardUrl = await createBoard(interviewerPage, "Delete Test");
    await addCard(interviewerPage, "To Do", "Doomed card");

    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    await gotoAndAwaitLiveConnection(candidatePage, boardUrl);
    await expect(candidatePage.getByText("Doomed card")).toBeVisible();

    await interviewerPage.getByRole("button", { name: "Delete card" }).click();

    await expect(candidatePage.getByText("Doomed card")).not.toBeVisible();

    await candidatePage.reload();
    await expect(candidatePage.getByText("Doomed card")).not.toBeVisible();

    await interviewer.close();
    await candidate.close();
  });

  test("renaming a board broadcasts live", async ({ browser }) => {
    const interviewer = await browser.newContext();
    const interviewerPage = await interviewer.newPage();
    const boardUrl = await createBoard(interviewerPage, "Old board name");

    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    await gotoAndAwaitLiveConnection(candidatePage, boardUrl);

    await interviewerPage.getByRole("button", { name: "Rename board" }).click();
    const nameInput = interviewerPage.locator("header input");
    await nameInput.fill("New board name");
    await nameInput.press("Enter");

    await expect(candidatePage.getByRole("heading", { name: "New board name" })).toBeVisible();

    await interviewer.close();
    await candidate.close();
  });

  test("a client joining mid-session sees existing state via REST, then live updates via WebSocket", async ({
    browser,
  }) => {
    const interviewer = await browser.newContext();
    const interviewerPage = await interviewer.newPage();
    const boardUrl = await createBoard(interviewerPage, "Join Mid Session Test");
    await addCard(interviewerPage, "To Do", "Existed before join");

    // Joins only now — this card must come from the initial REST fetch,
    // not a WebSocket event it could never have received.
    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    await gotoAndAwaitLiveConnection(candidatePage, boardUrl);
    await expect(candidatePage.getByText("Existed before join")).toBeVisible();

    // A change from here on must reach it live, over the socket it opened
    // on load.
    await addCard(interviewerPage, "To Do", "Added after join");
    await expect(candidatePage.getByText("Added after join")).toBeVisible();

    await interviewer.close();
    await candidate.close();
  });
});
