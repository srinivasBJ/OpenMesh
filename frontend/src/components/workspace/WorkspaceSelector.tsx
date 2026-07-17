import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { workspacesApi } from "@/api";
import { useWorkspaceStore } from "@/store/workspaceStore";

/**
 * Workspace switcher for the Event Bus card. Changing it rescopes Graph,
 * Feed, Agents, History, and the live event count to that workspace.
 */
export default function WorkspaceSelector({ onCreate }: { onCreate: () => void }) {
  const { activeWorkspaceId, setActiveWorkspace } = useWorkspaceStore();
  const { data: workspaces = [] } = useQuery({
    queryKey: ["workspaces"],
    queryFn: workspacesApi.list,
    refetchInterval: 15000,
  });

  return (
    <div className="mt-3 flex items-center gap-2">
      <select
        className="om-select h-9 min-w-0 flex-1 text-sm"
        aria-label="Active workspace"
        value={activeWorkspaceId ?? ""}
        onChange={(event) => {
          if (event.target.value === "__create__") {
            event.target.value = activeWorkspaceId ?? "";
            onCreate();
            return;
          }
          setActiveWorkspace(event.target.value || null);
        }}
      >
        <option value="">All workspaces</option>
        {workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            {workspace.kind === "demo" ? "◦ " : ""}{workspace.name} ({workspace.agent_count})
          </option>
        ))}
        <option value="__create__">＋ Create Workspace…</option>
      </select>
      <button
        type="button"
        className="om-button-ghost h-9 w-9 shrink-0 p-0"
        aria-label="Create workspace or project"
        title="Create workspace / project"
        onClick={onCreate}
      >
        <Plus size={15} />
      </button>
    </div>
  );
}
