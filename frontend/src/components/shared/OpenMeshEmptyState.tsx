import type { ReactNode } from "react";
import RotatingOrb from "@/components/shared/RotatingOrb";

interface OpenMeshEmptyStateProps {
  title: string;
  description: string;
  asset?: "wheel" | "mascot";
  children?: ReactNode;
}

export default function OpenMeshEmptyState({ title, description, asset = "wheel", children }: OpenMeshEmptyStateProps) {
  return (
    <div className={asset === "mascot" ? "om-mascot-card p-8 text-center" : "om-empty"}>
      {asset === "mascot" ? (
        <img src="/brand/agentpedia-mascot.svg" alt="" className="mx-auto h-28 w-auto object-contain" />
      ) : (
        <RotatingOrb size={80} className="mx-auto opacity-90 drop-shadow-[0_0_16px_rgba(190,92,36,.32)]" />
      )}
      <div className="om-kicker mt-4">Awaiting Signal</div>
      <h2 className="mt-2 text-xl font-bold text-[color:var(--om-text)]">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[color:var(--om-muted)]">{description}</p>
      {children ? <div className="mt-5">{children}</div> : null}
    </div>
  );
}
