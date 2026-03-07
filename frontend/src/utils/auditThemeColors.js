/**
 * Script to audit theme colors for WCAG AA compliance
 * Run with: node frontend/src/utils/auditThemeColors.js
 */

import { auditThemeContrast } from "./colorContrast.js";

// Light theme colors from index.css
const lightTheme = {
  background: "255 255 255", // white
  foreground: "15 23 42", // slate-900
  card: "248 250 252", // slate-50
  cardForeground: "15 23 42", // slate-900
  primary: "3 105 161", // sky-700
  primaryForeground: "255 255 255", // white
  secondary: "226 232 240", // slate-200
  secondaryForeground: "30 41 59", // slate-800
  muted: "241 245 249", // slate-100
  mutedForeground: "100 116 139", // slate-500
  accent: "240 249 255", // sky-50
  accentForeground: "3 105 161", // sky-700
  border: "226 232 240", // slate-200
};

// Dark theme colors from index.css
const darkTheme = {
  background: "15 23 42", // slate-900
  foreground: "248 250 252", // slate-50
  card: "30 41 59", // slate-800
  cardForeground: "248 250 252", // slate-50
  primary: "56 189 248", // sky-400
  primaryForeground: "15 23 42", // slate-900
  secondary: "51 65 85", // slate-700
  secondaryForeground: "226 232 240", // slate-200
  muted: "51 65 85", // slate-700
  mutedForeground: "148 163 184", // slate-400
  accent: "30 58 138", // blue-900
  accentForeground: "224 242 254", // sky-100
  border: "51 65 85", // slate-700
};

console.log("=== LIGHT THEME AUDIT ===\n");
const lightResults = auditThemeContrast(lightTheme);
lightResults.forEach((result) => {
  const status = result.passes ? "✓ PASS" : "✗ FAIL";
  console.log(`${status} ${result.name}`);
  console.log(`  Ratio: ${result.ratio}:1 (required: ${result.required}:1)`);
  console.log(`  Text: rgb(${result.text})`);
  console.log(`  Background: rgb(${result.background})\n`);
});

console.log("\n=== DARK THEME AUDIT ===\n");
const darkResults = auditThemeContrast(darkTheme);
darkResults.forEach((result) => {
  const status = result.passes ? "✓ PASS" : "✗ FAIL";
  console.log(`${status} ${result.name}`);
  console.log(`  Ratio: ${result.ratio}:1 (required: ${result.required}:1)`);
  console.log(`  Text: rgb(${result.text})`);
  console.log(`  Background: rgb(${result.background})\n`);
});

// Summary
const lightFails = lightResults.filter((r) => !r.passes).length;
const darkFails = darkResults.filter((r) => !r.passes).length;

console.log("\n=== SUMMARY ===");
console.log(
  `Light theme: ${lightResults.length - lightFails}/${lightResults.length} passed`,
);
console.log(
  `Dark theme: ${darkResults.length - darkFails}/${darkResults.length} passed`,
);

if (lightFails > 0 || darkFails > 0) {
  console.log(
    "\n⚠️  Some color combinations need adjustment for WCAG AA compliance",
  );
  process.exit(1);
} else {
  console.log("\n✓ All color combinations meet WCAG AA standards!");
  process.exit(0);
}
