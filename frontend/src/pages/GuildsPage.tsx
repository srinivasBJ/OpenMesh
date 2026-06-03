import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, X, Users, BookOpen, Star, Terminal } from "lucide-react";
import { guildsApi } from "@/api";
import { brandText, cn } from "@/lib/utils";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import toast from "react-hot-toast";

const DOMAINS = ["science", "engineering", "arts", "economics", "philosophy", "history", "exploration", "diplomacy"];
const GUILD_EMOJIS = ["🏛️", "🔬", "⚙️", "🎨", "📊", "🧠", "📜", "🧭", "🤝", "🌐", "⚔️", "🛡️"];
const GUILD_COLORS = ["#df742d", "#b9551f", "#d9a441", "#53606a", "#31564b", "#9aa5aa", "#873816", "#c94831"];

export default function GuildsPage() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", domain: "science", emoji: "🏛️", color: "#6366f1" });
  const [creating, setCreating] = useState(false);

  const { data: guilds = [], isLoading } = useQuery({
    queryKey: ["guilds"],
    queryFn: guildsApi.list,
  });

  const create = async () => {
    if (!form.name.trim()) return toast.error("Enter a guild name");
    setCreating(true);
    try {
      await guildsApi.create(form);
      toast.success(`${form.emoji} ${form.name} founded!`);
      qc.invalidateQueries({ queryKey: ["guilds"] });
      setShowCreate(false);
      setForm({ name: "", description: "", domain: "science", emoji: "🏛️", color: "#6366f1" });
    } catch {
      toast.error("Failed to create guild");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="om-page">
      <div className="om-page-narrow space-y-6">
      <div className="om-panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="om-kicker">Coordination Cells</div>
          <h1 className="om-title flex items-center gap-2 text-2xl">
            <Layers size={22} className="text-[color:var(--om-rust-400)]" /> Guilds
          </h1>
          <p className="mt-1 text-sm text-[color:var(--om-muted)]">Agent groups and operating domains observed by OpenMesh</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus size={15} /> Found Guild
        </button>
      </div>

      {isLoading ? (
        <OpenMeshLoading label="Loading guild registry" />
      ) : guilds.length === 0 ? (
        <OpenMeshEmptyState
          title="No guilds have formed yet"
          description="Guilds appear when the simulation or examples create agent coordination groups."
        >
          <div className="inline-flex items-center gap-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-3 py-2 text-xs text-[color:var(--om-steel-300)]">
            <Terminal size={13} /> Run a showcase scenario
          </div>
        </OpenMeshEmptyState>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {guilds.map((guild: any) => {
            const guildColor = guild.color || "#df742d";
            return (
            <div key={guild.id} className="card om-card-interactive p-5">
              <div className="flex items-start gap-3 mb-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-[6px] border text-2xl"
                  style={{ backgroundColor: `${guildColor}20`, border: `1px solid ${guildColor}66` }}>
                  {guild.emoji || "◆"}
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-white text-sm">{guild.name || "Unnamed guild"}</h3>
                  <p className="text-xs text-[color:var(--om-muted)] capitalize">{guild.domain || "domain unknown"}</p>
                  <div className="flex items-center gap-1 mt-0.5">
                    <Star size={10} className="text-[color:var(--om-amber-500)]" />
                    <span className="text-xs text-[color:var(--om-muted)]">{Number(guild.reputation || 0).toFixed(0)} rep</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-[color:var(--om-steel-300)] leading-relaxed mb-4">{brandText(guild.description, "No guild metadata recorded.")}</p>

              <div className="flex flex-wrap gap-3 border-t border-[color:var(--om-border)] pt-3 text-xs text-[color:var(--om-muted)]">
                <span className="flex items-center gap-1"><Users size={11} /> {guild.member_count} members</span>
                <span className="flex items-center gap-1"><BookOpen size={11} /> {guild.wiki_pages} pages</span>
                <span>{guild.total_discoveries || 0} discoveries</span>
              </div>
            </div>
          );
          })}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">Found a Guild</h2>
              <button onClick={() => setShowCreate(false)} className="text-[color:var(--om-muted)] hover:text-white" aria-label="Close create guild dialog"><X size={18} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Guild Name</label>
                <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Order of Quantum Minds"
                  className="om-input" />
              </div>
              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Description</label>
                <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                  placeholder="What does this guild pursue?"
                  rows={2}
                  className="om-textarea resize-none" />
              </div>
              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Domain</label>
                <select value={form.domain} onChange={e => setForm({ ...form, domain: e.target.value })}
                  className="om-select">
                  {DOMAINS.map(d => <option key={d} value={d} className="capitalize">{d}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Emoji</label>
                <div className="flex gap-2 flex-wrap">
                  {GUILD_EMOJIS.map(e => (
                    <button key={e} onClick={() => setForm({ ...form, emoji: e })}
                      className={cn("flex h-9 w-9 items-center justify-center rounded-[4px] border text-lg transition-colors",
                        form.emoji === e ? "border-[color:var(--om-border-strong)] bg-[rgba(90,36,16,.5)]" : "border-[color:var(--om-border)] bg-black/35 hover:bg-black/60")}>
                      {e}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Color</label>
                <div className="flex gap-2">
                  {GUILD_COLORS.map(c => (
                    <button key={c} onClick={() => setForm({ ...form, color: c })}
                      className={cn("h-7 w-7 rounded-[4px] border border-black/50 transition-transform", form.color === c ? "scale-110 ring-2 ring-[color:var(--om-rust-300)]" : "")}
                      style={{ backgroundColor: c }} />
                  ))}
                </div>
              </div>
              <button onClick={create} disabled={creating} className="w-full btn-primary py-2.5 disabled:opacity-50">
                {creating ? "Founding guild..." : `${form.emoji} Found ${form.name || "Guild"}`}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
