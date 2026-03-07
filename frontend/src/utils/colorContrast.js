/**
 * Color contrast utilities for WCAG compliance
 * WCAG AA requires:
 * - Normal text: 4.5:1 minimum
 * - Large text (18pt+ or 14pt+ bold): 3:1 minimum
 */

/**
 * Convert RGB values (0-255) to relative luminance
 * @param {number} r - Red value (0-255)
 * @param {number} g - Green value (0-255)
 * @param {number} b - Blue value (0-255)
 * @returns {number} Relative luminance (0-1)
 */
function getLuminance(r, g, b) {
  // Convert to 0-1 range
  const [rs, gs, bs] = [r, g, b].map((val) => {
    const s = val / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });

  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Calculate contrast ratio between two colors
 * @param {string} color1 - RGB string like "255 255 255" or hex like "#ffffff"
 * @param {string} color2 - RGB string like "15 23 42" or hex like "#0f172a"
 * @returns {number} Contrast ratio (1-21)
 */
export function getContrastRatio(color1, color2) {
  const rgb1 = parseColor(color1);
  const rgb2 = parseColor(color2);

  const lum1 = getLuminance(rgb1.r, rgb1.g, rgb1.b);
  const lum2 = getLuminance(rgb2.r, rgb2.g, rgb2.b);

  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);

  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Parse color string to RGB object
 * @param {string} color - RGB string like "255 255 255" or hex like "#ffffff"
 * @returns {{r: number, g: number, b: number}}
 */
function parseColor(color) {
  // Handle RGB space-separated format (from CSS custom properties)
  if (/^\d+\s+\d+\s+\d+$/.test(color.trim())) {
    const [r, g, b] = color.trim().split(/\s+/).map(Number);
    return { r, g, b };
  }

  // Handle hex format
  if (color.startsWith("#")) {
    const hex = color.replace("#", "");
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return { r, g, b };
  }

  throw new Error(`Unsupported color format: ${color}`);
}

/**
 * Check if contrast ratio meets WCAG AA standards
 * @param {number} ratio - Contrast ratio
 * @param {boolean} isLargeText - Whether text is large (18pt+ or 14pt+ bold)
 * @returns {boolean} Whether ratio meets WCAG AA
 */
export function meetsWCAG_AA(ratio, isLargeText = false) {
  return isLargeText ? ratio >= 3 : ratio >= 4.5;
}

/**
 * Audit all theme color combinations
 * @param {Object} theme - Theme object with color properties
 * @returns {Array} Array of audit results
 */
export function auditThemeContrast(theme) {
  const results = [];

  // Define text/background combinations to check
  const combinations = [
    {
      name: "Normal text on background",
      text: theme.foreground,
      bg: theme.background,
      isLarge: false,
    },
    {
      name: "Card text on card background",
      text: theme.cardForeground,
      bg: theme.card,
      isLarge: false,
    },
    {
      name: "Primary text on primary background",
      text: theme.primaryForeground,
      bg: theme.primary,
      isLarge: false,
    },
    {
      name: "Secondary text on secondary background",
      text: theme.secondaryForeground,
      bg: theme.secondary,
      isLarge: false,
    },
    {
      name: "Muted text on background",
      text: theme.mutedForeground,
      bg: theme.background,
      isLarge: false,
    },
    {
      name: "Accent text on accent background",
      text: theme.accentForeground,
      bg: theme.accent,
      isLarge: false,
    },
  ];

  for (const combo of combinations) {
    const ratio = getContrastRatio(combo.text, combo.bg);
    const passes = meetsWCAG_AA(ratio, combo.isLarge);

    results.push({
      name: combo.name,
      ratio: ratio.toFixed(2),
      required: combo.isLarge ? 3.0 : 4.5,
      passes,
      text: combo.text,
      background: combo.bg,
    });
  }

  return results;
}
