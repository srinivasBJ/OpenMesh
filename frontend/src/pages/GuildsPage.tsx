import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Atom,
  BarChart3,
  BookOpen,
  Brain,
  Compass,
  Handshake,
  Layers,
  Palette,
  Plus,
  ScrollText,
  ShieldCheck,
  Star,
  Terminal,
  Users,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { guildsApi } from "@/api";
import { brandText, cn } from "@/lib/utils";
import OpenMeshEmptyState from "@/components/shared/OpenMeshEmptyState";
import OpenMeshLoading from "@/components/shared/OpenMeshLoading";
import toast from "react-hot-toast";

const DOMAINS = ["science", "engineering", "arts", "economics", "philosophy", "history", "exploration", "diplomacy"];
const GUILD_COLORS = ["#df742d", "#b9551f", "#d9a441", "#53606a", "#31564b", "#9aa5aa", "#873816", "#c94831"];
const DEFAULT_GUILD_COLOR = "#df742d";
const DEFAULT_GUILD_MARK = "◆";

const DOMAIN_EMBLEMS: Record<string, LucideIcon> = {
  science: Atom,
  engineering: Wrench,
  arts: Palette,
  economics: BarChart3,
  philosophy: Brain,
  history: ScrollText,
  exploration: Compass,
  diplomacy: Handshake,
};

export default function GuildsPage() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    domain: "science",
    emoji: DEFAULT_GUILD_MARK,
    color: DEFAULT_GUILD_COLOR,
  });
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
      toast.success(`${form.name} added to the guild registry`);
      qc.invalidateQueries({ queryKey: ["guilds"] });
      setShowCreate(false);
      setForm({ name: "", description: "", domain: "science", emoji: DEFAULT_GUILD_MARK, color: DEFAULT_GUILD_COLOR });
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
        <OpenMeshLoading label="Loading guild registry" asset="mascot" />
      ) : guilds.length === 0 ? (
        <OpenMeshEmptyState
          asset="mascot"
          title="No guilds have formed yet"
          description="Guilds appear when observed agents form coordination groups or examples create operating cells."
        >
          <div className="inline-flex items-center gap-2 rounded-[4px] border border-[color:var(--om-border)] bg-black/45 px-3 py-2 text-xs text-[color:var(--om-steel-300)]">
            <Terminal size={13} /> Run a showcase scenario
          </div>
        </OpenMeshEmptyState>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {guilds.map((guild: any) => {
            const guildColor = guild.color || DEFAULT_GUILD_COLOR;
            return (
            <div key={guild.id} className="card om-card-interactive p-5">
              <div className="flex items-start gap-3 mb-3">
                <GuildEmblem domain={guild.domain} color={guildColor} />
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
              <div className="rounded-[6px] border border-[color:var(--om-border)] bg-black/30 p-3">
                <div className="flex items-center gap-3">
                  <GuildEmblem domain={form.domain} color={form.color} />
                  <div>
                    <div className="om-kicker">Industrial Guild Emblem</div>
                    <p className="text-xs text-[color:var(--om-muted)]">Emblems are generated from operating domain and signal color.</p>
                  </div>
                </div>
              </div>
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
                <label className="text-xs text-[color:var(--om-muted)] block mb-1.5">Signal Color</label>
                <div className="flex gap-2">
                  {GUILD_COLORS.map(c => (
                    <button key={c} onClick={() => setForm({ ...form, color: c })}
                      aria-label={`Use guild signal color ${c}`}
                      className={cn("h-7 w-7 rounded-[4px] border border-black/50 transition-transform", form.color === c ? "scale-110 ring-2 ring-[color:var(--om-rust-300)]" : "")}
                      style={{ backgroundColor: c }} />
                  ))}
                </div>
              </div>
              <button onClick={create} disabled={creating} className="w-full btn-primary py-2.5 disabled:opacity-50">
                {creating ? "Founding guild..." : `Found ${form.name || "Guild"}`}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

function GuildEmblem({ domain, color }: { domain?: string; color: string }) {
  const Icon = DOMAIN_EMBLEMS[String(domain || "").toLowerCase()] || ShieldCheck;

  return (
    <div
      className="relative flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-[6px] border bg-black/45"
      style={{ borderColor: `${color}88`, boxShadow: `inset 0 0 0 1px rgba(255,255,255,.04), 0 0 18px ${color}22` }}
    >
      <div className="absolute inset-0 opacity-25" style={{ background: `linear-gradient(135deg, ${color}44, transparent 58%)` }} />
      <div className="absolute left-1 top-1 h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      <Icon size={20} className="relative z-10" style={{ color }} />
    </div>
  );
}
