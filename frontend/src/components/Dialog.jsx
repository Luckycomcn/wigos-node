import { useEffect } from "react";

export default function Dialog({ open, title, onClose, children }) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog-panel" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h4>{title}</h4>
          <button type="button" className="dialog-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        <div className="dialog-body">{children}</div>
      </div>
    </div>
  );
}
