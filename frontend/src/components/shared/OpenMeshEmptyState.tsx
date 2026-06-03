import type { ReactNode } from "react";

interface OpenMeshEmptyStateProps {
  title: string;
  description: string;
  asset?: "wheel" | "mascot";
  children?: ReactNode;
}

export default function OpenMeshEmptyState({ title, description, asset = "wheel", children }: OpenMeshEmptyStateProps) {
  const image = asset === "mascot" ? "/brand/agentpedia-mascot.svg" : "/brand/openmesh-wheel.png";
  return (
    <div className={asset === "mascot" ? "om-mascot-card p-8 text-center" : "om-empty"}>
      <img src={image} alt="" className={asset === "mascot" ? "mx-auto h-28 w-auto object-contain" : "mx-auto h-16 w-16 rounded-[8px] object-cover opacity-85"} />
      <div className="om-kicker mt-4">Awaiting Signal</div>
      <h2 className="mt-2 text-xl font-bold text-[color:var(--om-text)]">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[color:var(--om-muted)]">{description}</p>
      {children ? <div className="mt-5">{children}</div> : null}
    </div>
  );
}
