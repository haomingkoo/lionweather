/**
 * Audit specific component color combinations
 * This checks the actual colors used in components, including semi-transparent overlays
 */

import { getContrastRatio, meetsWCAG_AA } from "./colorContrast.js";

// Helper to simulate alpha blending
function blendColors(foreground, background, alpha) {
  const fg = parseRGB(foreground);
  const bg = parseRGB(background);

  return {
    r: Math.round(fg.r * alpha + bg.r * (1 - alpha)),
    g: Math.round(fg.g * alpha + bg.g * (1 - alpha)),
    b: Math.round(fg.b * alpha + bg.b * (1 - alpha)),
  };
}

function parseRGB(color) {
  const [r, g, b] = color.split(/\s+/).map(Number);
  return { r, g, b };
}

function rgbToString(rgb) {
  return `${rgb.r} ${rgb.g} ${rgb.b}`;
}

console.log("=== COMPONENT COLOR AUDIT ===\n");

// Test 1: ThemeToggle label text
console.log("1. ThemeToggle label text");
const lightBg = "255 255 255";
const darkBg = "15 23 42";
const grayText = "55 65 81"; // gray-700
const grayTextDark = "209 213 219"; // gray-300

let ratio = getContrastRatio(grayText, lightBg);
console.log(
  `  Light mode: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}`,
);

ratio = getContrastRatio(grayTextDark, darkBg);
console.log(
  `  Dark mode: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}\n`,
);

// Test 2: LocationList text on semi-transparent white background
console.log("2. LocationList text on semi-transparent card (light mode)");
// Assuming gradient background is approximately rgb(200, 220, 240) - light blue
const gradientBg = "200 220 240";
// bg-white/25 = white with 25% opacity on gradient
const cardBg = blendColors("255 255 255", gradientBg, 0.25);
const cardBgStr = rgbToString(cardBg);
const textOnCard = "15 23 42"; // slate-900

ratio = getContrastRatio(textOnCard, cardBgStr);
console.log(
  `  Text on card: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}`,
);

// Secondary text
const secondaryText = "51 65 85"; // slate-700
ratio = getContrastRatio(secondaryText, cardBgStr);
console.log(
  `  Secondary text: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}\n`,
);

// Test 3: LocationList text on semi-transparent white background (dark mode)
console.log("3. LocationList text on semi-transparent card (dark mode)");
// Assuming gradient background is approximately rgb(30, 50, 80) - dark blue
const darkGradientBg = "30 50 80";
// bg-white/10 = white with 10% opacity on dark gradient
const darkCardBg = blendColors("255 255 255", darkGradientBg, 0.1);
const darkCardBgStr = rgbToString(darkCardBg);
const textOnDarkCard = "248 250 252"; // slate-50

ratio = getContrastRatio(textOnDarkCard, darkCardBgStr);
console.log(
  `  Text on card: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}`,
);

// Secondary text with 80% opacity
const secondaryTextDark = "248 250 252"; // slate-50 at 80% opacity
const blendedSecondary = blendColors(secondaryTextDark, darkCardBgStr, 0.8);
ratio = getContrastRatio(rgbToString(blendedSecondary), darkCardBgStr);
console.log(
  `  Secondary text (80% opacity): ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}\n`,
);

// Test 4: Error messages
console.log("4. Error message text");
const errorBgLight = blendColors("239 68 68", gradientBg, 0.3); // red-500/30
const errorTextLight = "127 29 29"; // red-900
const errorTextDark = "254 242 242"; // red-50

ratio = getContrastRatio(errorTextLight, rgbToString(errorBgLight));
console.log(
  `  Light mode: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}`,
);

const errorBgDark = blendColors("239 68 68", darkGradientBg, 0.4); // red-500/40
ratio = getContrastRatio(errorTextDark, rgbToString(errorBgDark));
console.log(
  `  Dark mode: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}\n`,
);

// Test 5: Button text
console.log("5. Button text on semi-transparent backgrounds");
const buttonBgLight = blendColors("255 255 255", gradientBg, 0.3); // white/30
ratio = getContrastRatio(textOnCard, rgbToString(buttonBgLight));
console.log(
  `  Light mode button: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}`,
);

const buttonBgDark = blendColors("255 255 255", darkGradientBg, 0.15); // white/15
ratio = getContrastRatio(textOnDarkCard, rgbToString(buttonBgDark));
console.log(
  `  Dark mode button: ${ratio.toFixed(2)}:1 ${meetsWCAG_AA(ratio) ? "✓ PASS" : "✗ FAIL"}\n`,
);

console.log(
  "Note: These tests use approximate gradient backgrounds. Actual contrast may vary based on weather condition gradients.",
);
