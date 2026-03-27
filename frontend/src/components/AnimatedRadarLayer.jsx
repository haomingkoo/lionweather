import { useEffect, useState, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { getRadarFrames } from "../api/radar";
import { RainfallOverlay } from "./RainfallOverlay";

/**
 * AnimatedRadarLayer Component
 *
 * Displays animated radar imagery showing rainfall patterns over time.
 * Uses native Leaflet imageOverlay (same approach as PrecipitationMap)
 * so frame updates are reliable across all browsers.
 *
 * Requirements: 1.1, 1.3, 1.7, 6.1, 6.2, 6.3, 6.5, 10.2
 */
export function AnimatedRadarLayer({
  visible = true,
  animationSpeed = 500,
  isPlaying = true,
  forcedIndex = null,       // Externally set frame index (slider scrub)
  onError,
  onFrameChange,
  onFramesLoaded,           // (count, timestamps[]) called once frames are ready
}) {
  const [frames, setFrames] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [preloadedImages, setPreloadedImages] = useState([]);
  const map = useMap();
  const intervalRef = useRef(null);
  const overlayRef = useRef(null);  // native Leaflet overlay instance

  // Constrain animation speed to 300-1000ms (Requirement 1.7)
  const constrainedSpeed = Math.max(300, Math.min(1000, animationSpeed));

  // Fetch radar frames on mount and every 5 minutes (Requirement 1.4)
  useEffect(() => {
    if (!visible) return;

    const fetchFrames = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const data = await getRadarFrames();

        if (!data || !data.frames || data.frames.length === 0) {
          throw new Error("No radar frames available");
        }

        console.log("[Radar] Fetched", data.frames.length, "frames from API");

        setFrames(data.frames);

        // Preload all images before starting animation (Requirement 6.2)
        await preloadImages(data.frames);

        setIsLoading(false);
      } catch (err) {
        console.error("[Radar] Failed to fetch frames:", err);
        setError(err.message || "Failed to load radar animation");
        setIsLoading(false);

        if (onError) {
          onError(err);
        }
      }
    };

    fetchFrames();

    // Refresh every 5 minutes (Requirement 1.4)
    const refreshInterval = setInterval(fetchFrames, 5 * 60 * 1000);

    return () => clearInterval(refreshInterval);
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  // Preload all frame images before starting animation (Requirement 6.2, 6.3)
  const preloadImages = async (frameList) => {
    const promises = frameList.map((frame) => {
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          console.log("[Radar] Preloaded frame:", frame.imageUrl);
          resolve(frame);
        };
        img.onerror = () => {
          console.warn("[Radar] Failed to preload frame:", frame.imageUrl);
          resolve(null);
        };
        img.src = frame.imageUrl;
      });
    });

    const results = await Promise.all(promises);
    const successfulFrames = results.filter((f) => f !== null);

    console.log("[Radar] Preloaded", successfulFrames.length, "of", frameList.length, "frames");

    if (successfulFrames.length === 0) {
      throw new Error("Failed to preload any radar images");
    }

    setPreloadedImages(successfulFrames);

    // Notify parent how many frames loaded and their timestamps
    if (onFramesLoaded) {
      onFramesLoaded(
        successfulFrames.length,
        successfulFrames.map((f) => f.timestamp),
      );
    }
  };

  // When parent scrubs the slider, jump to that frame
  useEffect(() => {
    if (forcedIndex !== null && preloadedImages.length > 0) {
      const idx = Math.max(0, Math.min(forcedIndex, preloadedImages.length - 1));
      setCurrentIndex(idx);
      if (onFrameChange && preloadedImages[idx]) {
        onFrameChange(preloadedImages[idx].timestamp);
      }
    }
  }, [forcedIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // Animation loop with setInterval (Requirement 6.2, 1.3)
  useEffect(() => {
    if (!isPlaying || preloadedImages.length === 0 || !visible) {
      return;
    }

    // Start animation loop
    intervalRef.current = setInterval(() => {
      setCurrentIndex((prevIndex) => {
        const nextIndex = (prevIndex + 1) % preloadedImages.length;
        // Notify parent of frame change
        if (onFrameChange && preloadedImages[nextIndex]) {
          onFrameChange(preloadedImages[nextIndex].timestamp, nextIndex);
        }
        return nextIndex;
      });
    }, constrainedSpeed);

    // Cleanup on unmount (Requirement 6.2)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isPlaying, preloadedImages, constrainedSpeed, visible, onFrameChange]);

  // Render current frame using native Leaflet imageOverlay (same as PrecipitationMap)
  // This approach is more reliable than React-Leaflet's <ImageOverlay> component.
  useEffect(() => {
    if (!map || !visible || preloadedImages.length === 0) {
      // Remove overlay if not visible
      if (overlayRef.current) {
        map && map.removeLayer(overlayRef.current);
        overlayRef.current = null;
      }
      return;
    }

    const currentFrame = preloadedImages[currentIndex];
    if (!currentFrame) return;

    const bounds = currentFrame.bounds || [[1.1550, 103.565], [1.4750, 104.130]];

    // Remove previous overlay
    if (overlayRef.current) {
      map.removeLayer(overlayRef.current);
      overlayRef.current = null;
    }

    // Add new native Leaflet imageOverlay
    const overlay = L.imageOverlay(currentFrame.imageUrl, bounds, {
      opacity: 0.7,
      zIndex: 1000,
      crossOrigin: true,
    });
    overlay.addTo(map);
    overlayRef.current = overlay;
  }, [map, currentIndex, preloadedImages, visible]);

  // Don't render if not visible
  if (!visible) {
    return null;
  }

  // Show nothing during preload (silent)
  if (isLoading) {
    return null;
  }

  // Fallback to static RainfallOverlay on error (Requirement 10.2, 6.3)
  if (error || preloadedImages.length === 0) {
    return <RainfallOverlay visible={visible} />;
  }

  // All rendering is done imperatively via the useEffect above — no JSX overlay needed
  return null;
}
