import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderGit2, Loader2, X } from "lucide-react";
import { providersApi, workspacesApi } from "@/api";
import { useWorkspaceStore } from "@/store/workspaceStore";

const AGENT_TYPES = ["", "Research Agent", "Coding Agent", "Observer Agent"];

/**
 * Create Workspace / Project flow: name + repository, optionally bound to a
 * connected provider/model, optionally spawning a typed agent into the
 * project. New workspace names are created on the fly.
 */
export default function CreateProjectModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { setActiveWorkspace } = useWorkspaceStore();
  const { data: workspaces = [] } = useQuery({ queryKey: ["workspaces"], queryFn: workspacesApi.list });
  const { data: providerStatus } = useQuery({ queryKey: ["providers"], queryFn: providersApi.list });

  const [workspaceChoice, setWorkspaceChoice] = useState("__new__");
  const [workspaceName, setWorkspaceName] = useState("");
  const [name, setName] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [agentType, setAgentType] = useState("");
  const [error, setError] = useState("");

  const configured = providerStatus?.providers.filter((p) => p.configured && !p.is_local) ?? [];

  const create = useMutation({
    mutationFn: () =>
      workspacesApi.createProject({
        workspace_id: workspaceChoice !== "__new__" ? workspaceChoice : undefined,
        workspace_name: workspaceChoice === "__new__" ? workspaceName.trim() : undefined,
        name: name.trim(),
        repository_path: repoPath.trim() || undefined,
        github_url: githubUrl.trim() || undefined,
        provider: provider || undefined,
        model: model.trim() || undefined,
        agent_type: agentType || undefined,
      }),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["workspaces"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
      if (result?.workspace?.id) setActiveWorkspace(result.workspace.id);
      onClose();
    },
    onError: (err: any) => setError(err?.response?.data?.detail || "Creating the project failed"),
  });

  const valid =
    name.trim().length > 0 &&
    (workspaceChoice !== "__new__" || workspaceName.trim().length > 0);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm">
      <div className="om-card max-h-[90vh] w-full max-w-lg overflow-y-auto p-7">
        <div className="flex items-start justify-between">
          <div>
            <div className="om-kicker">Workspace / Project</div>
            <h1 className="text-2xl font-black text-[color:var(--om-text)]">Create Project</h1>
          </div>
          <button type="button" className="om-button-ghost h-9 w-9 p-0" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form
          className="mt-5 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (valid) create.mutate();
          }}
        >
          <label className="block">
            <span className="om-kicker">Workspace</span>
            <select
              className="om-select mt-2 w-full"
              value={workspaceChoice}
              onChange={(event) => setWorkspaceChoice(event.target.value)}
            >
              <option value="__new__">+ New workspace…</option>
              {workspaces
                .filter((w) => w.kind !== "demo")
                .map((w) => (
                  <option key={w.id} value={w.id}>{w.name}</option>
                ))}
            </select>
          </label>

          {workspaceChoice === "__new__" ? (
            <label className="block">
              <span className="om-kicker">Workspace name</span>
              <input
                className="om-input mt-2 w-full"
                placeholder="AI Research Lab"
                value={workspaceName}
                onChange={(event) => setWorkspaceName(event.target.value)}
              />
            </label>
          ) : null}

          <label className="block">
            <span className="om-kicker">Project name</span>
            <input
              className="om-input mt-2 w-full"
              placeholder="Laser Detection"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>

          <label className="block">
            <span className="om-kicker">Repository path</span>
            <div className="relative mt-2">
              <FolderGit2 size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--om-dim)]" />
              <input
                className="om-input w-full pl-9"
                placeholder="~/Desktop/s1"
                value={repoPath}
                onChange={(event) => setRepoPath(event.target.value)}
              />
            </div>
          </label>

          <label className="block">
            <span className="om-kicker">GitHub URL (optional)</span>
            <input
              className="om-input mt-2 w-full"
              placeholder="https://github.com/…"
              value={githubUrl}
              onChange={(event) => setGithubUrl(event.target.value)}
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="om-kicker">Provider</span>
              <select
                className="om-select mt-2 w-full"
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
              >
                <option value="">None</option>
                {configured.map((p) => (
                  <option key={p.provider} value={p.provider}>{p.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="om-kicker">Model</span>
              <input
                className="om-input mt-2 w-full font-mono text-sm"
                placeholder="from Provider Manager"
                value={model}
                onChange={(event) => setModel(event.target.value)}
              />
            </label>
          </div>

          <label className="block">
            <span className="om-kicker">Agent type</span>
            <select
              className="om-select mt-2 w-full"
              value={agentType}
              onChange={(event) => setAgentType(event.target.value)}
            >
              {AGENT_TYPES.map((type) => (
                <option key={type} value={type}>{type || "No agent yet"}</option>
              ))}
            </select>
          </label>

          {error ? <div className="rounded-[4px] border border-red-700 px-3 py-2 text-sm text-red-400">{error}</div> : null}

          <button type="submit" className="om-button w-full" disabled={!valid || create.isPending}>
            {create.isPending ? <Loader2 size={15} className="animate-spin" /> : null}
            Create
          </button>
        </form>
      </div>
    </div>
  );
}
