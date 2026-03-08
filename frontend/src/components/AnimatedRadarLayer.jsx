import { useEffect, useState, useRef } from "react";
import { ImageOverlay, useMap } from "react-leaflet";
import { getRadarFrames } from "../api/radar";
import { RainfallOverlay } from "./RainfallOverlay";

/**
 * AnimatedRadarLayer Component
 *
 * Displays animated radar imagery showing rainfall patterns over time.
 * Features:
 * - Fetches radar frames from backend API
 * - Preloads all images before starting animation
 * - Cycles through frames with configurable speed (300-1000ms)
 * - Pauses animation when map not visible
 * - Falls back to static RainfallOverlay on error
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

        if (!data.frames || data.frames.length === 0) {
          throw new Error("No radar frames available");
        }

        setFrames(data.frames);

        // Preload all images before starting animation (Requirement 6.2)
        await preloadImages(data.frames);

        setIsLoading(false);
      } catch (err) {
        console.error("Failed to fetch radar frames:", err);
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
  }, [visible, onError]);

  // Preload all frame images before starting animation (Requirement 6.2, 6.3)
  const preloadImages = async (frameList) => {
    const promises = frameList.map((frame) => {
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(frame);
        img.onerror = () => {
          // Silently skip failed images
          resolve(null);
        };
        img.src = frame.imageUrl;
      });
    });

    try {
      const results = await Promise.all(promises);
      const successfulFrames = results.filter((f) => f !== null);
      setPreloadedImages(successfulFrames);

      if (successfulFrames.length === 0) {
        throw new Error("Failed to preload any radar images");
      }

      // Notify parent how many frames loaded and their timestamps
      if (onFramesLoaded) {
        onFramesLoaded(
          successfulFrames.length,
          successfulFrames.map((f) => f.timestamp),
        );
      }
    } catch (err) {
      throw err;
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
          onFrameChange(preloadedImages[nextIndex].timestamp);
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

  // Don't render if not visible
  if (!visible) {
    return null;
  }

  // Show loading indicator during preload (Requirement 6.3)
  if (isLoading) {
    return null; // Silent loading, no visual indicator needed
  }

  // Fallback to static RainfallOverlay on error (Requirement 10.2, 6.3)
  if (error || preloadedImages.length === 0) {
    // Silently fallback - don't spam console
    return <RainfallOverlay visible={visible} />;
  }

  // Get current frame
  const currentFrame = preloadedImages[currentIndex];

  if (!currentFrame) {
    // Fallback if current frame is invalid
    return <RainfallOverlay visible={visible} />;
  }

  // Render animated radar overlay (Requirement 1.1, 1.2)
  return (
    <ImageOverlay
      url={currentFrame.imageUrl}
      bounds={currentFrame.bounds}
      opacity={0.6}
      zIndex={1000}
    />
  );
}
