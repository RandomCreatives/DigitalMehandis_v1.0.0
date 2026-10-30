"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useProjectStore } from "@/store/projectStore";
import { api } from "@/lib/api";
import type { BBSBar, BBSBarCreate, BarShape, CuttingListItem, Section } from "@/types";
import { calcCuttingLength, calcWeight, calcLapLength } from "@/lib/calculations";
import { Plus, Trash2, FileSpreadsheet, ChevronDown, Layers } from "lucide-react";
import { cn } from "@/lib/utils";

const DIAMETERS = [6, 8, 10, 12, 16, 20, 25, 32];
const SHAPES: BarShape[] = ["STRAIGHT", "L_SHAPE", "HOOK", "U_SHAPE", "SPIRAL"];
const SECTIONS: Section[] = ["SUBSTRUCTURE", "SUPERSTRUCTURE"];

const SHAPE_ICON: Record<string, string> = {
  STRAIGHT: "—", L_SHAPE: "⌐", HOOK: "↩", U_SHAPE: "U", SPIRAL: "⟳",
};

const EMPTY: BBSBarCreate = {
  member_name: "", bar_diameter_mm: 16, bar_shape: "STRAIGHT",
  quantity: 1, clear_length_m: 1.0, hook_length_mm: 0,
  cover_top_mm: 50, cover_bottom_mm: 50, section: "SUBSTRUCTURE", standard: "ES_EN_1992_1_1", concrete_grade: "C25/30",
};

export default function BBSPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { current, fetchProject } = useProjectStore();
  const [bars, setBars]               = useState<BBSBar[]>([]);
  const [cuttingList, setCuttingList] = useState<CuttingListItem[]>([]);
  const [form, setForm]               = useState<BBSBarCreate>(EMPTY);
  const [activeSection, setActiveSection] = useState<Section>("SUBSTRUCTURE");
  const [showCutting, setShowCutting] = useState(false);
  const [pushingToBoq, setPushingToBoq] = useState(false);
  const [pushResult, setPushResult] = useState<string | null>(null);

  useEffect(() => { fetchProject(projectId); }, [projectId, fetchProject]);

  async function load() {
    const [barsRes, clRes] = await Promise.all([
      api.get(`/projects/${projectId}/bbs`),
      api.get(`/projects/${projectId}/bbs/cutting-list`),
    ]);
    setBars(barsRes.data);
    setCuttingList(clRes.data);
  }
  useEffect(() => { load(); }, [projectId]);

  const previewCutting = calcCuttingLength(form.bar_shape, form.clear_length_m, form.bar_diameter_mm, form.hook_length_mm, Math.max(form.cover_top_mm ?? 50, form.cover_bottom_mm ?? 50));
  const previewWeight  = calcWeight(form.bar_diameter_mm, previewCutting);
  const previewLap     = (() => {
    try {
      return `${calcLapLength(form.bar_diameter_mm, form.standard, form.concrete_grade)} mm`;
    } catch (err) {
      return (err as Error).message;
    }
  })();

  async function addBar(e: React.FormEvent) {
    e.preventDefault();
    const { data } = await api.post(`/projects/${projectId}/bbs`, form);
    setBars((prev) => [...prev, data]);
    const cl = await api.get(`/projects/${projectId}/bbs/cutting-list`);
    setCuttingList(cl.data);
    setForm({ ...EMPTY, section: form.section });
  }

  async function deleteBar(id: string) {
    await api.delete(`/projects/${projectId}/bbs/${id}`);
    setBars((prev) => prev.filter((b) => b.id !== id));
    const cl = await api.get(`/projects/${projectId}/bbs/cutting-list`);
    setCuttingList(cl.data);
  }

  async function exportExcel() {
    const res = await api.post(`/projects/${projectId}/bbs/export-excel`, {}, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url; a.download = "BBS.xlsx"; a.click();
  }

  async function pushToBoq() {
    setPushingToBoq(true);
    setPushResult(null);
    try {
      const { data } = await api.post(
        `/projects/${projectId}/bbs/sync-to-boq?section=${activeSection}`
      );
      setPushResult(`✓ ${data.message}`);
    } catch {
      setPushResult("Failed to sync to suggestions");
    } finally {
      setPushingToBoq(false);
    }
  }

  function upd(field: keyof BBSBarCreate, value: unknown) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  const filtered    = bars.filter((b) => b.section === activeSection);
  const totalWeight = filtered.reduce((sum, b) => sum + (b.total_weight_kg ?? 0), 0);

  // Weight by diameter for chart
  const weightByDia = cuttingList.reduce<Record<number, number>>((acc, item) => {
    acc[item.diameter_mm] = (acc[item.diameter_mm] ?? 0) + item.total_weight_kg;
    return acc;
  }, {});
  const totalAllWeight = Object.values(weightByDia).reduce((a, b) => a + b, 0);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 p-6 space-y-5 max-w-7xl mx-auto w-full overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-title-sm text-on-surface">Bar Bending Schedule</h2>
            <span className="chip chip-draft">ASTM A615</span>
          </div>
          <div className="flex items-center gap-2">
            {SECTIONS.map((s) => (
              <button key={s} onClick={() => setActiveSection(s)}
                className={cn("section-tab", activeSection === s ? "active" : "inactive")}>
                {s.charAt(0) + s.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-5">
          {/* Left: form + table */}
          <div className="col-span-2 space-y-5">
            {/* Add bar form */}
            <div className="card">
              <h3 className="font-semibold text-on-surface mb-4">Add Bar — {activeSection}</h3>
              <form onSubmit={addBar} className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="col-span-2">
                  <label className="block text-label-caps text-on-surface-variant mb-1">Member Name</label>
                  <input className="input" placeholder="e.g. Footing F1" value={form.member_name}
                    onChange={(e) => upd("member_name", e.target.value)} required />
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Diameter (mm)</label>
                  <select className="input" value={form.bar_diameter_mm} onChange={(e) => upd("bar_diameter_mm", parseInt(e.target.value))}>
                    {DIAMETERS.map((d) => <option key={d}>Ø {d}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Shape</label>
                  <select className="input" value={form.bar_shape} onChange={(e) => upd("bar_shape", e.target.value as BarShape)}>
                    {SHAPES.map((s) => <option key={s} value={s}>{SHAPE_ICON[s]} {s.replace("_", " ")}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Quantity</label>
                  <input type="number" min={1} className="input" value={form.quantity}
                    onChange={(e) => upd("quantity", parseInt(e.target.value))} required />
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Clear Length</label>
                  <div className="relative">
                    <input type="number" step="0.001" min={0} className="input pr-8" value={form.clear_length_m}
                      onChange={(e) => upd("clear_length_m", parseFloat(e.target.value))} required />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-label-caps text-on-surface-variant pointer-events-none">m</span>
                  </div>
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Hook Length</label>
                  <div className="relative">
                    <input type="number" min={0} className="input pr-10" value={form.hook_length_mm}
                      onChange={(e) => upd("hook_length_mm", parseInt(e.target.value))} />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-label-caps text-on-surface-variant pointer-events-none">mm</span>
                  </div>
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Cover (mm)</label>
                  <input type="number" min={0} className="input" value={form.cover_top_mm}
                    onChange={(e) => { upd("cover_top_mm", parseInt(e.target.value)); upd("cover_bottom_mm", parseInt(e.target.value)); }} />
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Standard</label>
                  <select className="input" value={form.standard} onChange={(e) => upd("standard", e.target.value)}>
                    <option value="ES_EN_1992_1_1">ES EN 1992-1-1:2015 (EC2)</option>
                    <option value="EBCS_2">EBCS-2:1995 (site practice)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-label-caps text-on-surface-variant mb-1">Concrete grade</label>
                  {/* Convention matters: "C-25" is f_cu=25 under EBCS-2 but
                      f_ck,cyl=25 under EC2 — two different mixes. */}
                  <input className="input" placeholder="C25/30" value={form.concrete_grade ?? ""}
                    onChange={(e) => upd("concrete_grade", e.target.value)} />
                </div>

                {/* Live preview */}
                <div className="col-span-2 md:col-span-4 bg-primary/5 border border-primary/10 rounded-lg p-3 grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-on-surface-variant text-xs">Cutting Length</span>
                    <p className="font-bold text-on-surface">{previewCutting.toFixed(3)} m</p>
                  </div>
                  <div>
                    <span className="text-on-surface-variant text-xs">Weight / unit</span>
                    <p className="font-bold text-on-surface">{previewWeight.toFixed(3)} kg</p>
                  </div>
                  <div>
                    <span className="text-on-surface-variant text-xs">Lap Length</span>
                    <p className="font-bold text-on-surface">{previewLap}</p>
                  </div>
                </div>

                <div className="col-span-2 md:col-span-4 flex justify-end gap-2">
                  <button onClick={exportExcel} type="button" className="btn-secondary flex items-center gap-2">
                    <FileSpreadsheet size={14} /> Export Excel
                  </button>
                  <button
                    type="button"
                    onClick={pushToBoq}
                    disabled={pushingToBoq || filtered.length === 0}
                    className="btn-secondary flex items-center gap-2 disabled:opacity-40"
                  >
                    <Layers size={14} /> {pushingToBoq ? "Syncing…" : "Sync to Suggestions"}
                  </button>
                  <button type="submit" className="btn-primary flex items-center gap-2">
                    <Plus size={15} /> Add Bar
                  </button>
                </div>
                {pushResult && (
                  <div className="col-span-2 md:col-span-4">
                    <p className={`text-sm px-3 py-2 rounded-lg ${pushResult.startsWith("✓") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                      {pushResult}
                    </p>
                  </div>
                )}
              </form>
            </div>

            {/* BBS Table */}
            <div className="panel overflow-x-auto">
              <div className="px-4 py-3 border-b border-outline-variant flex items-center justify-between">
                <h3 className="font-semibold text-on-surface">BBS — {activeSection}</h3>
                <span className="text-sm text-on-surface-variant">
                  Total: <strong className="text-on-surface">{totalWeight.toFixed(2)} kg</strong>
                </span>
              </div>
              <table className="data-table text-xs">
                <thead>
                  <tr>
                    <th>Mark</th>
                    <th>Member</th>
                    <th>Shape</th>
                    <th className="num">Ø mm</th>
                    <th className="num">Qty</th>
                    <th className="num">Clear (m)</th>
                    <th className="num">Cut (m)</th>
                    <th className="num">Wt/unit</th>
                    <th className="num">Total Wt</th>
                    <th className="num">Lap mm</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr><td colSpan={11} className="text-center py-10 text-on-surface-variant">No bars yet.</td></tr>
                  ) : filtered.map((bar) => (
                    <tr key={bar.id}>
                      <td className="font-semibold text-accent">{bar.bar_mark}</td>
                      <td className="font-medium text-on-surface">{bar.member_name}</td>
                      <td className="text-on-surface-variant">{SHAPE_ICON[bar.bar_shape]} {bar.bar_shape.replace("_", " ")}</td>
                      <td className="num">Ø{bar.bar_diameter_mm}</td>
                      <td className="num">{bar.quantity}</td>
                      <td className="num">{Number(bar.clear_length_m).toFixed(3)}</td>
                      <td className="num font-semibold">{bar.cutting_length_m?.toFixed(3)}</td>
                      <td className="num">{bar.weight_per_unit_kg?.toFixed(3)}</td>
                      <td className="num font-bold text-on-surface">{bar.total_weight_kg?.toFixed(3)}</td>
                      <td className="num">{bar.lap_length_mm}</td>
                      <td>
                        <button onClick={() => deleteBar(bar.id)} className="btn-ghost p-1 text-error" aria-label="Delete">
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                {filtered.length > 0 && (
                  <tfoot>
                    <tr>
                      <td colSpan={8} className="text-right font-bold text-on-surface uppercase text-xs">Total Weight</td>
                      <td className="num text-accent font-bold">{totalWeight.toFixed(2)} kg</td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>

            {/* Cutting list toggle */}
            <button onClick={() => setShowCutting(!showCutting)}
              className="btn-ghost flex items-center gap-2 text-sm font-semibold">
              <ChevronDown size={16} className={cn("transition-transform", showCutting && "rotate-180")} />
              {showCutting ? "Hide" : "Show"} Full BBS Detailed Report
            </button>

            {showCutting && cuttingList.length > 0 && (
              <div className="panel overflow-x-auto">
                <div className="px-4 py-3 border-b border-outline-variant">
                  <h3 className="font-semibold text-on-surface">Cutting List (for supplier)</h3>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Diameter</th>
                      <th className="num">Cutting Length (m)</th>
                      <th className="num">Total Qty</th>
                      <th className="num">Total Weight (kg)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cuttingList.map((item, i) => (
                      <tr key={i}>
                        <td className="font-semibold text-on-surface">Ø{item.diameter_mm}mm</td>
                        <td className="num">{item.cutting_length_m.toFixed(3)}</td>
                        <td className="num">{item.total_qty}</td>
                        <td className="num font-bold">{item.total_weight_kg.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Right: BBS cards + weight chart */}
          <div className="space-y-4">
            {/* Bar cards */}
            {filtered.slice(0, 3).map((bar) => (
              <div key={bar.id} className="card py-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-label-caps text-on-surface-variant">Bar Mark: {bar.bar_mark}</p>
                    <p className="text-xs text-on-surface-variant">Member: {bar.member_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                  <span className="font-mono">{SHAPE_ICON[bar.bar_shape]}</span>
                  <span>Shape: {bar.bar_shape.replace("_", " ")}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-on-surface">Ø {bar.bar_diameter_mm}mm</span>
                  <span className="chip chip-progress">{bar.total_weight_kg?.toFixed(1)} kg</span>
                </div>
              </div>
            ))}

            {/* Weight by diameter */}
            {totalAllWeight > 0 && (
              <div className="card bg-primary text-white py-4 space-y-3">
                <p className="text-label-caps text-white/60 uppercase">Reinforcement Weight by Diameter</p>
                {Object.entries(weightByDia)
                  .sort(([a], [b]) => Number(b) - Number(a))
                  .map(([dia, wt]) => {
                    const pct = Math.round((wt / totalAllWeight) * 100);
                    return (
                      <div key={dia} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold">Ø {dia}mm</span>
                          <span className="text-white/70">{wt.toFixed(0)} kg ({pct}%)</span>
                        </div>
                        <div className="bg-white/20 rounded-full h-1.5">
                          <div className="bg-accent h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
