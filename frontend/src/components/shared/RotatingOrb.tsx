import { cn } from "@/lib/utils";

interface RotatingOrbProps {
  /** Pixel size of the orb (width and height). */
  size?: number;
  /** Milliseconds for one full revolution. */
  durationMs?: number;
  className?: string;
}

/**
 * The rotating OpenMesh wheel. Single source of truth for the orb everywhere
 * (sidebar, loading, empty states, graph) so every page animates consistently.
 * Rotation is a pure compositor-thread transform (see .om-orb in globals.css),
 * so it stays at 60fps and keeps spinning even when there is no data.
 */
export default function RotatingOrb({ size = 64, durationMs = 14000, className }: RotatingOrbProps) {
  return (
    <img
      src="/brand/openmesh-wheel-clean.png"
      alt=""
      aria-hidden="true"
      className={cn("om-orb object-contain", className)}
      style={{ width: size, height: size, animationDuration: `${durationMs}ms` }}
    />
  );
}
