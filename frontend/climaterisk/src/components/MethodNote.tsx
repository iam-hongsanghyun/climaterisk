import type { ReactNode } from "react";

/** A small, quiet explanatory block: how a number was derived + its data source. */
export function MethodNote({ title = "How this is computed", children }: { title?: string; children: ReactNode }) {
  return (
    <div className="method-note">
      <div className="method-note-title">ⓘ {title}</div>
      <div className="method-note-body">{children}</div>
    </div>
  );
}
