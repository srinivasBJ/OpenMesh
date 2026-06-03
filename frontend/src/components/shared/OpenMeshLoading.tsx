export default function OpenMeshLoading({ label = "Synchronizing OpenMesh" }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center">
      <div className="text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[8px] border border-[color:var(--om-border)] bg-black/50 shadow-[var(--om-glow-rust)]">
          <img src="/brand/openmesh-wheel.png" alt="" className="h-12 w-12 animate-spin rounded-[4px] object-cover [animation-duration:2400ms]" />
        </div>
        <div className="om-kicker mt-4">{label}</div>
      </div>
    </div>
  );
}
