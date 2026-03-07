import { useEffect, useState } from "react";

/**
 * AnimatedBackground Component
 *
 * Renders weather-based animated backgrounds:
 * - Clouds for cloudy weather
 * - Rain particles for rainy weather
 * - Stars for clear night conditions
 */
export function AnimatedBackground({ condition, isDark = false }) {
  const [animationType, setAnimationType] = useState("none");

  useEffect(() => {
    const conditionLower = condition?.toLowerCase() || "";
    const currentHour = new Date().getHours();
    const isNight = currentHour < 6 || currentHour > 18;

    if (conditionLower.includes("rain") || conditionLower.includes("shower")) {
      setAnimationType("rain");
    } else if (
      conditionLower.includes("cloud") ||
      conditionLower.includes("overcast")
    ) {
      setAnimationType("clouds");
    } else if (
      (conditionLower.includes("clear") ||
        conditionLower.includes("fair") ||
        conditionLower.includes("sunny")) &&
      isNight
    ) {
      setAnimationType("stars");
    } else {
      setAnimationType("none");
    }
  }, [condition]);

  if (animationType === "none") {
    return null;
  }

  return (
    <div
      className="fixed inset-0 pointer-events-none overflow-hidden"
      style={{ zIndex: 0 }}
      data-testid="animated-background"
    >
      {animationType === "clouds" && <CloudsAnimation isDark={isDark} />}
      {animationType === "rain" && <RainAnimation isDark={isDark} />}
      {animationType === "stars" && <StarsAnimation />}
    </div>
  );
}

function CloudsAnimation({ isDark }) {
  return (
    <div className="animated-clouds">
      {[...Array(5)].map((_, i) => (
        <div
          key={i}
          className={`cloud ${isDark ? "opacity-20" : "opacity-30"}`}
          style={{
            left: `${i * 25}%`,
            top: `${10 + i * 15}%`,
            animationDelay: `${i * 2}s`,
            animationDuration: `${20 + i * 5}s`,
          }}
        >
          <div className="cloud-part cloud-part-1"></div>
          <div className="cloud-part cloud-part-2"></div>
          <div className="cloud-part cloud-part-3"></div>
        </div>
      ))}
    </div>
  );
}

function RainAnimation({ isDark }) {
  return (
    <div className="rain-particles">
      {[...Array(50)].map((_, i) => (
        <div
          key={i}
          className={`rain-drop ${isDark ? "opacity-40" : "opacity-50"}`}
          style={{
            left: `${Math.random() * 100}%`,
            animationDelay: `${Math.random() * 2}s`,
            animationDuration: `${0.5 + Math.random() * 0.5}s`,
          }}
        ></div>
      ))}
    </div>
  );
}

function StarsAnimation() {
  return (
    <div className="stars-animation">
      {[...Array(100)].map((_, i) => (
        <div
          key={i}
          className="star"
          style={{
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            animationDelay: `${Math.random() * 3}s`,
            animationDuration: `${2 + Math.random() * 2}s`,
          }}
        ></div>
      ))}
    </div>
  );
}
