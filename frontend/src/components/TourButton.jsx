import { useEffect, useRef } from "react";
import { X } from "lucide-react";

// Quiet "30-second tour" link with a native <dialog> player; ?tour=1 opens it on load.
export function TourButton({ className = "" }) {
  const dialog = useRef(null);
  const video = useRef(null);
  const trigger = useRef(null);

  const open = () => {
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
  };
  const close = () => dialog.current?.close();

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("tour") === "1") open();
  }, []);

  const onClose = () => {
    video.current?.pause();
    trigger.current?.focus();
  };

  return (
    <>
      <button
        ref={trigger}
        type="button"
        onClick={open}
        className={`inline-flex min-h-6 items-center whitespace-nowrap text-xs text-muted underline-offset-2 hover:text-ink hover:underline ${className}`}
      >
        ▶ 30-second tour
      </button>
      <dialog
        ref={dialog}
        aria-labelledby="tour-title"
        onClose={onClose}
        onClick={(e) => e.target === dialog.current && close()}
        className="m-auto w-[calc(100%-2rem)] max-w-[960px] rounded-panel border border-line bg-surface p-0 text-ink backdrop:bg-black/70"
      >
        <div className="p-3 sm:p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 id="tour-title" className="text-sm font-semibold">LionWeather in 30 seconds</h2>
            <button type="button" onClick={close} aria-label="Close tour" className="grid h-8 w-8 place-items-center rounded-control text-muted hover:bg-surface-2 hover:text-ink">
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {/* ?v= skips edge copies of the SPA fallback cached before the media shipped. */}
          <video ref={video} controls preload="none" playsInline poster="/media/haze-poster.jpg?v=1" className="aspect-video w-full rounded-control bg-black">
            <source src="/media/haze.webm?v=1" type="video/webm" />
            <source src="/media/haze.mp4?v=1" type="video/mp4" />
          </video>
          <p className="mt-2 text-xs text-muted">Music: Sascha Ende, ende.app (CC BY 4.0)</p>
        </div>
      </dialog>
    </>
  );
}
