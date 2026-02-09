import { hc } from "hono/client";
import type { AppType } from "../../server/index.js";

const client = hc<AppType>("/");
export { client as api };
