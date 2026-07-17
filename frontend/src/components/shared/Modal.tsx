import { useCallback, useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

interface ModalProps {
  onClose: () => void;
  children: ReactNode;
  /** Tailwind max-width class for the card, e.g. "max-w-2xl". */
  maxWidth?: string;
  /** Extra classes for the card. */
  className?: string;
  /** Render the standard X close button (default true). */
  showClose?: boolean;
  "aria-label"?: string;
}

/**
 * Shared modal lifecycle for every OpenMesh dialog:
 * - Escape closes
 * - Clicking the backdrop (outside the card) closes
 * - X button closes
 * - Callers close programmatically after a successful action
 * The UI can never be left in a locked state that needs a refresh.
 */
export default function Modal({
  onClose,
  children,
  maxWidth = "max-w-lg",
  className = "",
  showClose = true,
  "aria-label": ariaLabel,
}: ModalProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const pressedOutside = useRef(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  // Track where the press started so a drag that ends on the backdrop
  // (e.g. selecting text inside the card) doesn't close the modal.
  const onBackdropMouseDown = useCallback((event: React.MouseEvent) => {
    pressedOutside.current = !cardRef.current?.contains(event.target as Node);
  }, []);

  const onBackdropClick = useCallback(
    (event: React.MouseEvent) => {
      const releasedOutside = !cardRef.current?.contains(event.target as Node);
      if (pressedOutside.current && releasedOutside) onClose();
      pressedOutside.current = false;
    },
    [onClose],
  );

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      onMouseDown={onBackdropMouseDown}
      onClick={onBackdropClick}
    >
      <div
        ref={cardRef}
        className={`om-card relative max-h-[90vh] w-full overflow-y-auto p-7 ${maxWidth} ${className}`}
      >
        {showClose ? (
          <button
            type="button"
            className="om-button-ghost absolute right-4 top-4 h-9 w-9 p-0"
            aria-label="Close"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        ) : null}
        {children}
      </div>
    </div>
  );
}
