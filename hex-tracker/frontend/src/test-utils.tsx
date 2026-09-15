import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { render } from "@testing-library/react";

import { routeTree } from "./routeTree.gen";

/** Renders the app's real router (routes, loaders, and all) at `path`, so
 * route components under test run with the same `Route.useParams()` /
 * `Route.useRouteContext()` wiring they have in production — just with an
 * in-memory history instead of the browser's, and a fresh QueryClient per
 * call so tests don't share a cache. */
export function renderAtPath(path: string) {
  // retry: false — otherwise a rejected query stays "loading" through
  // react-query's default retry/backoff, well past any reasonable test
  // timeout, before ever reaching an error state.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createRouter({
    routeTree,
    context: { queryClient },
    history: createMemoryHistory({ initialEntries: [path] }),
  });

  return { ...render(<RouterProvider router={router} />), router, queryClient };
}
