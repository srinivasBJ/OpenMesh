export default function OpenMeshLoading({ label = "Synchronizing OpenMesh", asset = "wheel" }: { label?: string; asset?: "wheel" | "mascot" }) {
  const image = asset === "mascot" ? "/brand/agentpedia-mascot.svg" : "/brand/openmesh-wheel-clean.png";
  return (
    <div className="flex min-h-48 items-center justify-center">
      <div className="text-center">
        <div className={asset === "mascot" ? "mx-auto flex h-20 w-20 items-center justify-center" : "mx-auto"}>
          <img
            src={image}
            alt=""
            className={asset === "mascot" ? "h-16 w-16 object-contain" : "mx-auto h-24 w-24 animate-spin object-contain [animation-duration:2600ms]"}
          />
        </div>
        <div className="om-kicker mt-4">{label}</div>
      </div>
    </div>
  );
}
