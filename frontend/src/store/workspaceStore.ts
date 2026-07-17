import { create } from "zustand";

const ACTIVE_WORKSPACE_KEY = "openmesh.workspace.active";

interface WorkspaceStore {
  /** null = all workspaces (no filter) */
  activeWorkspaceId: string | null;
  setActiveWorkspace: (id: string | null) => void;
}

/**
 * The active workspace scopes Graph, Feed, Agents, History, and the live
 * event bus. Persisted so the selection survives reloads.
 */
export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  activeWorkspaceId: window.localStorage.getItem(ACTIVE_WORKSPACE_KEY) || null,
  setActiveWorkspace: (id) => {
    if (id) window.localStorage.setItem(ACTIVE_WORKSPACE_KEY, id);
    else window.localStorage.removeItem(ACTIVE_WORKSPACE_KEY);
    set({ activeWorkspaceId: id });
  },
}));
