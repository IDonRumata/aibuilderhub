/**
 * Generate public/_redirects from src/data/tools.json.
 *
 * Every outbound tool link on the site points at /go/<id>. Cloudflare Pages
 * turns that into a 302 to the affiliate URL when one is configured, or to
 * the tool's own site when it is not. Swapping in a new affiliate link is a
 * one-line change in tools.json instead of a search-and-replace across 25
 * files, and no published post ever has to be edited again.
 *
 * Runs automatically via the `prebuild` npm script.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const { tools } = JSON.parse(
  readFileSync(resolve(root, "src/data/tools.json"), "utf8")
);

const lines = [
  "# GENERATED FILE - do not edit.",
  "# Source: src/data/tools.json, generator: scripts/build-redirects.mjs",
  "#",
  "# 302 rather than 301: affiliate destinations change, and a permanently",
  "# cached redirect in a reader's browser would keep sending them to an old",
  "# partner link long after it stopped paying.",
  "",
];

let monetised = 0;
for (const tool of tools) {
  const target = tool.affiliateUrl ?? tool.officialUrl;
  if (!target) {
    throw new Error(`tool "${tool.id}" has neither affiliateUrl nor officialUrl`);
  }
  if (tool.affiliateUrl) monetised += 1;
  lines.push(`/go/${tool.id}  ${target}  302`);
}

writeFileSync(resolve(root, "public/_redirects"), lines.join("\n") + "\n", "utf8");

console.log(
  `[redirects] ${tools.length} tool links written, ${monetised} monetised, ` +
    `${tools.length - monetised} still pointing at the vendor for free`
);
