import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { toast, Toaster, resolveValue, type Toast } from "react-hot-toast";
import { cn } from "@/lib/utils";

const ICONS = {
  blank: Info,
  custom: Info,
  success: CheckCircle2,
  error: XCircle,
  loading: AlertTriangle,
} as const;

const LABELS = {
  blank: "Info",
  custom: "Info",
  success: "Success",
  error: "Error",
  loading: "Working",
} as const;

export default function IndustrialToaster() {
  return (
    <Toaster
      position="top-center"
      gutter={10}
      containerClassName="om-alert-stack"
      toastOptions={{ duration: 4200 }}
    >
      {(item) => <IndustrialToast toastItem={item} />}
    </Toaster>
  );
}

function IndustrialToast({ toastItem }: { toastItem: Toast }) {
  const type = toastItem.type in ICONS ? toastItem.type : "blank";
  const Icon = ICONS[type as keyof typeof ICONS];
  return (
    <div
      className={cn(
        "om-alert-panel",
        toastItem.visible ? "translate-y-0 opacity-100" : "-translate-y-2 opacity-0",
        type === "error" && "om-alert-error",
        type === "success" && "om-alert-success",
        type === "loading" && "om-alert-warning",
      )}
      role={type === "error" ? "alert" : "status"}
    >
      <Icon size={17} className="shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="om-alert-label">{LABELS[type as keyof typeof LABELS]}</div>
        <div className="truncate text-sm text-[color:var(--om-text)]">{resolveValue(toastItem.message, toastItem)}</div>
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        className="rounded-[2px] border border-black/50 bg-black/25 p-1 text-current hover:bg-black/50"
        onClick={() => toast.dismiss(toastItem.id)}
      >
        <X size={14} />
      </button>
    </div>
  );
}
