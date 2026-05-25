import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const root = resolve(__dirname, "..");

const source = resolve(root, "public", ".htaccess");
const targetDir = resolve(root, "dist");
const target = resolve(targetDir, ".htaccess");

if (!existsSync(source)) {
  console.error("Missing source file:", source);
  process.exit(1);
}

if (!existsSync(targetDir)) {
  mkdirSync(targetDir, { recursive: true });
}

copyFileSync(source, target);
console.log("Copied .htaccess to dist for Hostinger deploy.");
