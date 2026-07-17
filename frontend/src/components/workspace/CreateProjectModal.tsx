import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, Check, Folder, FolderGit2, FolderOpen, Loader2 } from "lucide-react";
import { filesystemApi, providersApi, workspacesApi } from "@/api";
import Modal from "@/components/shared/Modal";
import { apiErrorMessage, refreshAppState } from "@/lib/appState";
import { useWorkspaceStore } from "@/store/workspaceStore";
import toast from "react-hot-toast";

const AGENT_TYPES = ["", "Research Agent", "Coding Agent", "Observer Agent"];

/**
 * Create Workspace / Project flow. The repository path can be typed or
 * picked with the built-in server-side directory browser (browsers can't
 * expose absolute paths from a native picker).
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
  const [browsing, setBrowsing] = useState(false);
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
      refreshAppState(qc);
      if (result?.workspace?.id) setActiveWorkspace(result.workspace.id);
      toast.success(`Project "${result?.project?.name ?? name}" created`);
      onClose(); // success → modal closes automatically
    },
    onError: (err) => setError(apiErrorMessage(err, "Creating the project failed")),
  });

  const valid =
    name.trim().length > 0 &&
    (workspaceChoice !== "__new__" || workspaceName.trim().length > 0);

  return (
    <Modal onClose={onClose} aria-label="Create workspace or project">
      <div className="pr-10">
        <div className="om-kicker">Workspace / Project</div>
        <h1 className="text-2xl font-black text-[color:var(--om-text)]">Create Project</h1>
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

        <div className="block">
          <span className="om-kicker">Repository path</span>
          <div className="mt-2 flex gap-2">
            <div className="relative flex-1">
              <FolderGit2 size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--om-dim)]" />
              <input
                className="om-input w-full pl-9"
                placeholder="~/Desktop/s1"
                value={repoPath}
                onChange={(event) => setRepoPath(event.target.value)}
              />
            </div>
            <button
              type="button"
              className="om-button-ghost px-3"
              title="Browse folders"
              onClick={() => setBrowsing((value) => !value)}
            >
              <FolderOpen size={15} /> Browse
            </button>
          </div>
          {browsing ? (
            <DirectoryBrowser
              onPick={(path) => {
                setRepoPath(path);
                setBrowsing(false);
              }}
            />
          ) : null}
        </div>

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
    </Modal>
  );
}

/** Server-side folder picker, restricted to the home directory. */
function DirectoryBrowser({ onPick }: { onPick: (path: string) => void }) {
  const [path, setPath] = useState<string | undefined>(undefined);
  const { data, isFetching, error } = useQuery({
    queryKey: ["filesystem", path ?? "~"],
    queryFn: () => filesystemApi.browse(path),
    retry: false,
  });

  return (
    <div className="mt-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 p-2">
      <div className="flex items-center gap-2 px-1 pb-2">
        <button
          type="button"
          className="om-button-ghost h-7 w-7 shrink-0 p-0"
          aria-label="Parent folder"
          disabled={!data?.parent}
          onClick={() => data?.parent && setPath(data.parent)}
        >
          <ArrowUp size={13} />
        </button>
        <code className="min-w-0 flex-1 truncate font-mono text-xs text-[color:var(--om-muted)]">
          {data?.path ?? "…"}
        </code>
        {data ? (
          <button type="button" className="om-button h-7 px-2 text-[11px]" onClick={() => onPick(data.path)}>
            <Check size={12} /> Use this folder
          </button>
        ) : null}
      </div>
      <div className="max-h-40 overflow-y-auto">
        {error ? (
          <div className="p-2 text-xs text-red-400">{apiErrorMessage(error, "Unable to browse folders.")}</div>
        ) : isFetching && !data ? (
          <div className="flex items-center gap-2 p-2 text-xs text-[color:var(--om-muted)]">
            <Loader2 size={12} className="animate-spin" /> Loading…
          </div>
        ) : data && data.directories.length === 0 ? (
          <div className="p-2 text-xs text-[color:var(--om-dim)]">No subfolders.</div>
        ) : (
          data?.directories.map((dir) => (
            <button
              key={dir.path}
              type="button"
              className="flex w-full items-center gap-2 rounded-[3px] px-2 py-1 text-left text-xs text-[color:var(--om-muted)] hover:bg-black/40 hover:text-[color:var(--om-text)]"
              onClick={() => setPath(dir.path)}
              onDoubleClick={() => onPick(dir.path)}
            >
              <Folder size={12} className="shrink-0 text-[color:var(--om-rust-400)]" />
              <span className="truncate">{dir.name}</span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
