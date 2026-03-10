import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = resolve(ROOT, "docusaurus.config.ts");

const configText = readFileSync(CONFIG_PATH, "utf-8");

const match = configText.match(/locales:\s*\[([^\]]+)\]/);
if (!match) {
  throw new Error("Could not find locales array in docusaurus.config.ts");
}

const allLocales = match[1]
  .split(",")
  .map((s) => s.trim().replace(/['"]/g, ""))
  .filter(Boolean);

const defaultMatch = configText.match(/defaultLocale:\s*['"]([^'"]+)['"]/);
if (!defaultMatch) {
  throw new Error("Could not find defaultLocale in docusaurus.config.ts");
}
const defaultLocale = defaultMatch[1];

const locales = allLocales.filter((l) => l !== defaultLocale);

console.log(
  `Found ${locales.length} non-default locales (default: ${defaultLocale})\n`
);

const failed: string[] = [];

for (const locale of locales) {
  const cmd = `npx docusaurus write-translations --locale ${locale}`;
  console.log(`[${locales.indexOf(locale) + 1}/${locales.length}] ${cmd}`);
  try {
    execSync(cmd, { cwd: ROOT, stdio: "inherit" });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`  FAILED: ${message}\n`);
    failed.push(locale);
  }
}

console.log(`\nDone. ${locales.length - failed.length}/${locales.length} succeeded.`);
if (failed.length > 0) {
  console.error(`Failed locales: ${failed.join(", ")}`);
  process.exit(1);
}
