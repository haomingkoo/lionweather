// Single source of truth for API base URL
const _rawBase = import.meta.env.VITE_API_BASE_URL || "";
const _secureBase = _rawBase.replace(/^http:\/\//, "https://");

// API_BASE includes /api suffix (used by most API modules)
export const API_BASE = _secureBase.startsWith("http") ? `${_secureBase}/api` : "/api";
