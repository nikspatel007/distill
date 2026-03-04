import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { RootLayout } from "./routes/__root.js";
import Dashboard from "./routes/index.js";
import GraphPage from "./routes/graph.js";
import Reading from "./routes/reading.js";
import ReadingDetail from "./routes/reading.$date.js";
import Share from "./routes/share.js";
import ShareDetail from "./routes/shares.$id.js";
import Shares from "./routes/shares.js";
import Studio from "./routes/studio.js";
import StudioDetail from "./routes/studio.$slug.js";
import Settings from "./routes/settings.js";

const rootRoute = createRootRoute({ component: RootLayout });

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
});

const readingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reading",
  component: Reading,
});

const readingDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reading/$date",
  component: ReadingDetail,
});

const shareRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/share",
  component: Share,
});

const sharesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/shares",
  component: Shares,
});

const shareDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/shares/$id",
  component: ShareDetail,
});

const studioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/studio",
  component: Studio,
});

const studioDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/studio/$slug",
  component: StudioDetail,
});

const graphRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/graph",
  component: GraphPage,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: Settings,
});

export const routeTree = rootRoute.addChildren([
  indexRoute,
  readingRoute,
  readingDetailRoute,
  shareRoute,
  sharesRoute,
  shareDetailRoute,
  studioRoute,
  studioDetailRoute,
  graphRoute,
  settingsRoute,
]);
