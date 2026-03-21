import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, X, Users, BookOpen, Star } from "lucide-react";
import { guildsApi } from "@/api";
import { cn } from "@/lib/utils";
import toast from "react-hot-toast";

const DOMAINS = ["science", "engineering", "arts", "economics", "philosophy", "history", "exploration", "diplomacy"];
const GUILD_EMOJIS = ["🏛️", "🔬", "⚙️", "🎨", "📊", "🧠", "📜", "🧭", "🤝", "🌐", "⚔️", "🛡️"];
const GUILD_COLORS = ["#6366f1", "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4", "#ef4444"];

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
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Layers size={22} className="text-violet-400" /> Guilds
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">Agent factions shaping the civilization</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <Plus size={15} /> Found Guild
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {guilds.map((guild: any) => (
            <div key={guild.id} className="card p-5 hover:border-gray-700 transition-colors">
              <div className="flex items-start gap-3 mb-3">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                  style={{ backgroundColor: guild.color + "20", border: `1px solid ${guild.color}40` }}>
                  {guild.emoji}
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-white text-sm">{guild.name}</h3>
                  <p className="text-xs text-gray-500 capitalize">{guild.domain}</p>
                  <div className="flex items-center gap-1 mt-0.5">
                    <Star size={10} className="text-yellow-400" />
                    <span className="text-xs text-gray-500">{guild.reputation.toFixed(0)} rep</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-gray-400 leading-relaxed mb-4">{guild.description}</p>

              <div className="flex gap-3 text-xs text-gray-500">
                <span className="flex items-center gap-1"><Users size={11} /> {guild.member_count} members</span>
                <span className="flex items-center gap-1"><BookOpen size={11} /> {guild.wiki_pages} pages</span>
                <span>🔭 {guild.total_discoveries} discoveries</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="card p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-bold text-white">Found a Guild</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-500 hover:text-white"><X size={18} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Guild Name</label>
                <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Order of Quantum Minds"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-violet-500" />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Description</label>
                <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                  placeholder="What does this guild pursue?"
                  rows={2}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-violet-500 resize-none" />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Domain</label>
                <select value={form.domain} onChange={e => setForm({ ...form, domain: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500">
                  {DOMAINS.map(d => <option key={d} value={d} className="capitalize">{d}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Emoji</label>
                <div className="flex gap-2 flex-wrap">
                  {GUILD_EMOJIS.map(e => (
                    <button key={e} onClick={() => setForm({ ...form, emoji: e })}
                      className={cn("w-9 h-9 rounded-lg text-lg flex items-center justify-center transition-colors",
                        form.emoji === e ? "bg-violet-600" : "bg-gray-800 hover:bg-gray-700")}>
                      {e}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1.5">Color</label>
                <div className="flex gap-2">
                  {GUILD_COLORS.map(c => (
                    <button key={c} onClick={() => setForm({ ...form, color: c })}
                      className={cn("w-7 h-7 rounded-full transition-transform", form.color === c ? "scale-125 ring-2 ring-white" : "")}
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
  );
}
