// Weather condition to gradient mapping - More vibrant Apple-style gradients
export function getWeatherGradient(condition, isDark = false) {
  const conditionLower = condition?.toLowerCase() || "";

  // Sunny/Clear - Bright warm gradient
  if (
    conditionLower.includes("sunny") ||
    conditionLower.includes("clear") ||
    conditionLower.includes("fair")
  ) {
    return isDark
      ? "from-yellow-600 via-orange-600 to-pink-700"
      : "from-yellow-400 via-orange-400 to-pink-500";
  }

  // Rainy - Cool blue gradient
  if (
    conditionLower.includes("rain") ||
    conditionLower.includes("shower") ||
    conditionLower.includes("drizzle")
  ) {
    return isDark
      ? "from-blue-700 via-cyan-700 to-teal-600"
      : "from-blue-500 via-cyan-500 to-teal-400";
  }

  // Thunderstorm - Dramatic dark gradient
  if (conditionLower.includes("thunder") || conditionLower.includes("storm")) {
    return isDark
      ? "from-indigo-950 via-purple-950 to-pink-950"
      : "from-indigo-900 via-purple-900 to-pink-900";
  }

  // Partly Cloudy - Mixed gradient
  if (conditionLower.includes("partly")) {
    return isDark
      ? "from-blue-600 via-sky-600 to-amber-600"
      : "from-blue-400 via-sky-300 to-amber-300";
  }

  // Cloudy - Soft gray gradient
  if (conditionLower.includes("cloud") || conditionLower.includes("overcast")) {
    return isDark
      ? "from-slate-600 via-gray-600 to-zinc-700"
      : "from-slate-300 via-gray-300 to-zinc-400";
  }

  // Default - Beautiful sky blue
  return isDark
    ? "from-sky-600 via-blue-700 to-indigo-700"
    : "from-sky-400 via-blue-500 to-indigo-500";
}

export function getWeatherIcon(condition) {
  const conditionLower = condition?.toLowerCase() || "";

  if (
    conditionLower.includes("sunny") ||
    conditionLower.includes("clear") ||
    conditionLower.includes("fair")
  ) {
    return "Sun";
  }

  if (
    conditionLower.includes("rain") ||
    conditionLower.includes("shower") ||
    conditionLower.includes("drizzle")
  ) {
    return "CloudRain";
  }

  if (conditionLower.includes("thunder") || conditionLower.includes("storm")) {
    return "CloudLightning";
  }

  if (conditionLower.includes("partly")) {
    return "CloudSun";
  }

  if (conditionLower.includes("cloud")) {
    return "Cloud";
  }

  if (conditionLower.includes("overcast")) {
    return "Cloudy";
  }

  return "CloudSun";
}

export function isDarkGradient(condition) {
  const conditionLower = condition?.toLowerCase() || "";
  return conditionLower.includes("thunder") || conditionLower.includes("storm");
}
