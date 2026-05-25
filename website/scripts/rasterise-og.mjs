#!/usr/bin/env node
/**
 * Rasterise public/og-image.svg → public/og-image.png at 1200×630.
 *
 * Why: most social crawlers (X/Twitter, LinkedIn, Slack, Discord previews)
 * either fall back, downsize, or refuse to render SVG og:image. PNG is the
 * universally supported fallback.
 *
 * Usage:
 *   npm install --save-optional sharp
 *   node scripts/rasterise-og.mjs
 *
 * Skips with a warning if `sharp` isn't installed so CI without native
 * dependencies doesn't fail. Run this once per OG-image change, commit the
 * resulting PNG alongside the SVG.
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");
const svgPath = resolve(root, "public", "og-image.svg");
const pngPath = resolve(root, "public", "og-image.png");

if (!existsSync(svgPath)) {
  console.warn(`og-image.svg not found at ${svgPath} — nothing to rasterise.`);
  process.exit(0);
}

let sharp;
try {
  ({ default: sharp } = await import("sharp"));
} catch {
  console.warn(
    "sharp not installed. Run `npm install --save-optional sharp` then re-run " +
      "this script to generate og-image.png. SVG fallback remains in meta tags.",
  );
  process.exit(0);
}

const svg = readFileSync(svgPath);
const out = await sharp(svg).resize(1200, 630, { fit: "contain", background: "#ffffff" }).png({ compressionLevel: 9 }).toBuffer();
writeFileSync(pngPath, out);
console.log(`Wrote ${pngPath} (${out.length} bytes).`);
