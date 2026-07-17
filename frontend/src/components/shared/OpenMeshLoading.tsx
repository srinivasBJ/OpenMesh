import RotatingOrb from "@/components/shared/RotatingOrb";

export default function OpenMeshLoading({ label = "Synchronizing OpenMesh", asset = "wheel" }: { label?: string; asset?: "wheel" | "mascot" }) {
  return (
    <div className="flex min-h-48 items-center justify-center">
      <div className="text-center">
        <div className="mx-auto flex items-center justify-center">
          {asset === "mascot" ? (
            <img src="/brand/agentpedia-mascot.svg" alt="" className="h-16 w-16 object-contain" />
          ) : (
            <RotatingOrb size={96} durationMs={2600} className="mx-auto" />
          )}
        </div>
        <div className="om-kicker mt-4">{label}</div>
      </div>
    </div>
  );
}
