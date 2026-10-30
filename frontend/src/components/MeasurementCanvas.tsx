"use client";
import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
// Fabric.js v5 exports as { fabric } — unwrap the namespace
import * as fabricModule from "fabric";
// Fabric's v5 typings are loose here; the rule this used to disable is not
// configured in this project, and naming an unknown rule is itself a lint error.
const fabric = (fabricModule as any).fabric as typeof import("fabric")["fabric"];
import * as pdfjsLib from "pdfjs-dist";
import { api as axiosApi } from "@/lib/api";
import {
  MousePointer2,
  Ruler,
  Minus,
  Square,
  Hash,
  ZoomIn,
  ZoomOut,
  Maximize2,
  X,
  Trash2,
  ArrowRight,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Calibration,
  SavedMeasurement,
  Tool,
  Discipline,
  Section,
} from "@/types/measurements";

// ── PDF.js worker ─────────────────────────────────────────────────────────────
if (typeof window !== "undefined") {
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url
  ).toString();
}

// ── Constants ─────────────────────────────────────────────────────────────────
const PRESET_COLORS = [
  "#eb6905",
  "#2563eb",
  "#16a34a",
  "#dc2626",
  "#7c3aed",
  "#0891b2",
];

const DISCIPLINES: Discipline[] = [
  "ARCHITECTURAL",
  "STRUCTURAL",
  "ELECTRICAL",
  "SANITARY",
];
const SECTIONS: Section[] = ["SUBSTRUCTURE", "SUPERSTRUCTURE"];

// ── Props ─────────────────────────────────────────────────────────────────────
export interface MeasurementCanvasProps {
  drawingId: string;
  projectId: string;
  blobUrl: string;
  drawingName: string;
  onClose: () => void;
}

// ── Project Element type ──────────────────────────────────────────────────────
interface ProjectElement {
  id: string;
  element_code: string;
  element_type: string;
  discipline: string;
  section: string;
}

// ── Pending measurement state ─────────────────────────────────────────────────
interface PendingMeasurement {
  type: "length" | "area" | "count";
  points: { x: number; y: number }[];
  rawValue: number;
  unit: string;
}

// ── Save form state ───────────────────────────────────────────────────────────
interface SaveForm {
  label: string;
  discipline: Discipline;
  section: Section;
  elementCategory: string;
  multiplier: number;
  color: string;
  project_element_id: string;
}

const DEFAULT_FORM: SaveForm = {
  label: "",
  discipline: "ARCHITECTURAL",
  section: "SUBSTRUCTURE",
  elementCategory: "",
  multiplier: 1.0,
  color: PRESET_COLORS[0],
  project_element_id: "",
};

// ── Toast ─────────────────────────────────────────────────────────────────────
interface Toast {
  id: number;
  message: string;
  type: "success" | "error";
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function dist(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2);
}

function polylineLength(pts: { x: number; y: number }[]) {
  let total = 0;
  for (let i = 0; i < pts.length - 1; i++) total += dist(pts[i], pts[i + 1]);
  return total;
}

function polygonArea(pts: { x: number; y: number }[]) {
  let area = 0;
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += pts[i].x * pts[j].y;
    area -= pts[j].x * pts[i].y;
  }
  return Math.abs(area) / 2;
}

function formatValue(
  rawPx: number,
  type: "length" | "area" | "count",
  calibration: Calibration | null
): { value: number; unit: string } {
  if (type === "count") return { value: rawPx, unit: "Nr" };
  if (!calibration) {
    return { value: Math.round(rawPx * 100) / 100, unit: type === "area" ? "px²" : "px" };
  }
  const sf = calibration.scale_factor; // meters per pixel
  if (type === "length") {
    return { value: Math.round(rawPx * sf * 1000) / 1000, unit: "m" };
  }
  // area
  return { value: Math.round(rawPx * sf * sf * 1000) / 1000, unit: "m²" };
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function MeasurementCanvas({
  drawingId,
  projectId,
  blobUrl,
  drawingName,
  onClose,
}: MeasurementCanvasProps) {
  // Canvas refs
  const pdfCanvasRef = useRef<HTMLCanvasElement>(null);
  const fabricCanvasRef = useRef<HTMLCanvasElement>(null);
  const fabricRef = useRef<fabric.Canvas | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // PDF state
  const [pageNumber] = useState(1);
  const [pdfDims, setPdfDims] = useState({ width: 0, height: 0 });

  // Tool state
  const [activeTool, setActiveTool] = useState<Tool>("select");
  const activeToolRef = useRef<Tool>("select");

  // Drawing state (refs for use inside event handlers)
  const drawingPointsRef = useRef<{ x: number; y: number }[]>([]);
  const tempObjectsRef = useRef<fabric.Object[]>([]);
  const calibPointsRef = useRef<{ x: number; y: number }[]>([]);
  const calibTempRef = useRef<fabric.Object[]>([]);
  const countRef = useRef(0);

  // Calibration
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const calibrationRef = useRef<Calibration | null>(null);

  // Calibration modal
  const [showCalibModal, setShowCalibModal] = useState(false);
  const [calibDistance, setCalibDistance] = useState("");
  const [calibUnit, setCalibUnit] = useState<"m" | "mm" | "cm">("m");
  const pendingCalibPointsRef = useRef<{ x: number; y: number }[]>([]);

  // Measurements
  const [measurements, setMeasurements] = useState<SavedMeasurement[]>([]);

  // Project Elements
  const [elements, setElements] = useState<ProjectElement[]>([]);

  // Pending measurement (finished drawing, awaiting save)
  const [pending, setPending] = useState<PendingMeasurement | null>(null);
  const pendingRef = useRef<PendingMeasurement | null>(null);

  // Save form
  const [saveForm, setSaveForm] = useState<SaveForm>(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);

  // Status bar
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  // Space-pan state
  const spaceDownRef = useRef(false);
  const panningRef = useRef(false);
  const lastPanRef = useRef({ x: 0, y: 0 });

  // ── Toast helpers ───────────────────────────────────────────────────────────
  const showToast = useCallback((message: string, type: "success" | "error" = "success") => {
    const id = ++toastIdRef.current;
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);

  // ── Sync refs ───────────────────────────────────────────────────────────────
  useEffect(() => { activeToolRef.current = activeTool; }, [activeTool]);
  useEffect(() => { calibrationRef.current = calibration; }, [calibration]);
  useEffect(() => { pendingRef.current = pending; }, [pending]);

  // ── Load calibration ────────────────────────────────────────────────────────
  const loadCalibration = useCallback(async () => {
    try {
      const { data } = await api.get(
        `/projects/${projectId}/drawings/${drawingId}/calibrations/active?page_number=${pageNumber}`
      );
      setCalibration(data ?? null);
    } catch {
      setCalibration(null);
    }
  }, [projectId, drawingId, pageNumber]);

  // ── Load measurements ───────────────────────────────────────────────────────
  const loadMeasurements = useCallback(async () => {
    try {
      const { data } = await api.get(
        `/projects/${projectId}/drawings/${drawingId}/measurements?page_number=${pageNumber}`
      );
      setMeasurements(data ?? []);
    } catch {
      // ignore
    }
  }, [projectId, drawingId, pageNumber]);

  // ── Load project elements ───────────────────────────────────────────────────
  const loadElements = useCallback(async () => {
    try {
      const { data } = await api.get(`/projects/${projectId}/elements`);
      setElements(data ?? []);
    } catch {
      // ignore
    }
  }, [projectId]);

  // ── Render PDF ──────────────────────────────────────────────────────────────
  const renderDxf = useCallback(async () => {
    if (!pdfCanvasRef.current) return;
    try {
      const { data } = await api.get(`/projects/${projectId}/drawings/${drawingId}/canvas-data`);
      const canvas = pdfCanvasRef.current;
      const ctx = canvas.getContext("2d")!;

      const vb = data.viewbox;
      const width = vb.max_x - vb.min_x;
      const height = vb.max_y - vb.min_y;
      const scale = 1000 / Math.max(width, height);

      canvas.width = width * scale;
      canvas.height = height * scale;
      ctx.strokeStyle = "#333";
      ctx.lineWidth = 1;

      for (const layer in data.layers) {
        for (const line of data.layers[layer].lines) {
          ctx.beginPath();
          ctx.moveTo((line.x1 - vb.min_x) * scale, (vb.max_y - line.y1) * scale);
          ctx.lineTo((line.x2 - vb.min_x) * scale, (vb.max_y - line.y2) * scale);
          ctx.stroke();
        }
      }
      setPdfDims({ width: canvas.width, height: canvas.height });
      return { width: canvas.width, height: canvas.height };
    } catch (err) {
      console.error("DXF render error", err);
    }
  }, [projectId, drawingId]);
  const renderPdf = useCallback(async () => {
    if (!pdfCanvasRef.current) return;
    try {
      const loadingTask = pdfjsLib.getDocument(blobUrl);
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1.5 });
      const canvas = pdfCanvasRef.current;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d")!;
      await page.render({ canvasContext: ctx, viewport }).promise;
      setPdfDims({ width: viewport.width, height: viewport.height });
      return { width: viewport.width, height: viewport.height };
    } catch (err) {
      console.error("PDF render error", err);
    }
  }, [blobUrl, pageNumber]);

  // ── Initialize Fabric + PDF ─────────────────────────────────────────────────
  useEffect(() => {
    let fc: fabric.Canvas | null = null;

    async function init() {
      const dims = drawingName.toLowerCase().endsWith(".dxf") ? await renderDxf() : await renderPdf();
      if (!dims || !fabricCanvasRef.current) return;

      fc = new fabric.Canvas(fabricCanvasRef.current, {
        selection: false,
        renderOnAddRemove: true,
        width: dims.width,
        height: dims.height,
      });
      fabricRef.current = fc;

      // Draw PDF as background image
      if (pdfCanvasRef.current) {
        const dataUrl = pdfCanvasRef.current.toDataURL("image/png");
        fabric.Image.fromURL(dataUrl, (img) => {
          fc!.setBackgroundImage(img, fc!.renderAll.bind(fc!), {
            scaleX: 1,
            scaleY: 1,
          });
        });
      }

      // ── Mouse events ──────────────────────────────────────────────────────
      fc.on("mouse:move", (opt) => {
        const pointer = fc!.getPointer(opt.e);
        setCoords({ x: Math.round(pointer.x), y: Math.round(pointer.y) });

        // Space-pan
        if (spaceDownRef.current && panningRef.current) {
          const e = opt.e as MouseEvent;
          const dx = e.clientX - lastPanRef.current.x;
          const dy = e.clientY - lastPanRef.current.y;
          fc!.relativePan(new fabric.Point(dx, dy));
          lastPanRef.current = { x: e.clientX, y: e.clientY };
          return;
        }

        // Live preview while drawing
        const tool = activeToolRef.current;
        const pts = drawingPointsRef.current;
        if ((tool === "length" || tool === "area") && pts.length > 0) {
          // Remove last temp preview line
          const last = tempObjectsRef.current[tempObjectsRef.current.length - 1];
          if (last && (last as fabric.Object & { _isPreview?: boolean })._isPreview) {
            fc!.remove(last);
            tempObjectsRef.current.pop();
          }
          const preview = new fabric.Line(
            [pts[pts.length - 1].x, pts[pts.length - 1].y, pointer.x, pointer.y],
            { stroke: "#999", strokeWidth: 1, strokeDashArray: [4, 4], selectable: false, evented: false }
          ) as fabric.Object & { _isPreview?: boolean };
          preview._isPreview = true;
          fc!.add(preview);
          tempObjectsRef.current.push(preview);
          fc!.renderAll();
        }

        // Calibrate preview
        if (tool === "calibrate" && calibPointsRef.current.length === 1) {
          const last = calibTempRef.current[calibTempRef.current.length - 1];
          if (last && (last as fabric.Object & { _isPreview?: boolean })._isPreview) {
            fc!.remove(last);
            calibTempRef.current.pop();
          }
          const preview = new fabric.Line(
            [calibPointsRef.current[0].x, calibPointsRef.current[0].y, pointer.x, pointer.y],
            { stroke: "#f97316", strokeWidth: 1.5, strokeDashArray: [6, 3], selectable: false, evented: false }
          ) as fabric.Object & { _isPreview?: boolean };
          preview._isPreview = true;
          fc!.add(preview);
          calibTempRef.current.push(preview);
          fc!.renderAll();
        }
      });

      fc.on("mouse:down", (opt) => {
        const e = opt.e as MouseEvent;
        // Middle mouse or space+left = pan start
        if (e.button === 1 || spaceDownRef.current) {
          panningRef.current = true;
          lastPanRef.current = { x: e.clientX, y: e.clientY };
          fc!.defaultCursor = "grabbing";
          return;
        }

        const pointer = fc!.getPointer(e);
        const tool = activeToolRef.current;

        if (tool === "calibrate") {
          handleCalibrateClick(pointer, fc!);
        } else if (tool === "length") {
          handleLengthClick(pointer, fc!);
        } else if (tool === "area") {
          handleAreaClick(pointer, fc!);
        } else if (tool === "count") {
          handleCountClick(pointer, fc!);
        }
      });

      fc.on("mouse:up", () => {
        panningRef.current = false;
        fc!.defaultCursor = activeToolRef.current === "select" ? "default" : "crosshair";
      });

      fc.on("mouse:dblclick", (opt) => {
        const tool = activeToolRef.current;
        if (tool === "length") finishLength(fc!);
        else if (tool === "area") finishArea(fc!);
      });

      // Wheel zoom
      fc.on("mouse:wheel", (opt) => {
        const delta = (opt.e as WheelEvent).deltaY;
        let z = fc!.getZoom();
        z *= 0.999 ** delta;
        z = Math.min(Math.max(z, 0.1), 10);
        fc!.zoomToPoint(new fabric.Point((opt.e as WheelEvent).offsetX, (opt.e as WheelEvent).offsetY), z);
        setZoom(Math.round(z * 100) / 100);
        opt.e.preventDefault();
        opt.e.stopPropagation();
      });

      await loadCalibration();
      await loadMeasurements();
      await loadElements();
    }

    init();

    // Keyboard listeners
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space") { spaceDownRef.current = true; e.preventDefault(); }
      if (e.code === "Escape") cancelDrawing();
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") { spaceDownRef.current = false; }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);

    return () => {
      fc?.dispose();
      fabricRef.current = null;
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blobUrl, pageNumber]);

  // ── Tool cursor ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const fc = fabricRef.current;
    if (!fc) return;
    fc.defaultCursor = activeTool === "select" ? "default" : "crosshair";
    fc.hoverCursor = activeTool === "select" ? "move" : "crosshair";
    if (activeTool !== "length" && activeTool !== "area" && activeTool !== "calibrate") {
      cancelDrawing();
    }
  }, [activeTool]);

  // ── Cancel drawing ──────────────────────────────────────────────────────────
  function cancelDrawing() {
    const fc = fabricRef.current;
    if (!fc) return;
    tempObjectsRef.current.forEach((o) => fc.remove(o));
    tempObjectsRef.current = [];
    calibTempRef.current.forEach((o) => fc.remove(o));
    calibTempRef.current = [];
    drawingPointsRef.current = [];
    calibPointsRef.current = [];
    setPending(null);
    fc.renderAll();
  }

  // ── Calibrate tool ──────────────────────────────────────────────────────────
  function handleCalibrateClick(pointer: { x: number; y: number }, fc: fabric.Canvas) {
    const pts = calibPointsRef.current;
    if (pts.length === 0) {
      // First point
      const dot = new fabric.Circle({
        left: pointer.x - 5,
        top: pointer.y - 5,
        radius: 5,
        fill: "#f97316",
        selectable: false,
        evented: false,
      });
      fc.add(dot);
      calibTempRef.current.push(dot);
      pts.push(pointer);
    } else if (pts.length === 1) {
      // Second point
      const dot = new fabric.Circle({
        left: pointer.x - 5,
        top: pointer.y - 5,
        radius: 5,
        fill: "#f97316",
        selectable: false,
        evented: false,
      });
      const line = new fabric.Line([pts[0].x, pts[0].y, pointer.x, pointer.y], {
        stroke: "#f97316",
        strokeWidth: 2,
        strokeDashArray: [8, 4],
        selectable: false,
        evented: false,
      });
      fc.add(line, dot);
      calibTempRef.current.push(line, dot);
      pts.push(pointer);
      pendingCalibPointsRef.current = [...pts];
      calibPointsRef.current = [];
      setShowCalibModal(true);
      fc.renderAll();
    }
  }

  // ── Confirm calibration ─────────────────────────────────────────────────────
  async function confirmCalibration() {
    const pts = pendingCalibPointsRef.current;
    if (pts.length < 2) return;
    const realDist = parseFloat(calibDistance);
    if (isNaN(realDist) || realDist <= 0) {
      showToast("Enter a valid distance", "error");
      return;
    }
    try {
      const { data } = await api.post(
        `/projects/${projectId}/drawings/${drawingId}/calibrations`,
        {
          page_number: pageNumber,
          point_a_x: pts[0].x,
          point_a_y: pts[0].y,
          point_b_x: pts[1].x,
          point_b_y: pts[1].y,
          real_distance: realDist,
          real_unit: calibUnit,
        }
      );
      setCalibration(data);
      showToast(`Calibrated: 1px = ${(data.scale_factor * 1000).toFixed(3)} mm`);
      setShowCalibModal(false);
      setCalibDistance("");
      // Keep calibration line on canvas (already drawn)
    } catch {
      showToast("Calibration failed", "error");
    }
  }

  function cancelCalibration() {
    setShowCalibModal(false);
    setCalibDistance("");
    cancelDrawing();
  }

  // ── Length tool ─────────────────────────────────────────────────────────────
  function handleLengthClick(pointer: { x: number; y: number }, fc: fabric.Canvas) {
    const pts = drawingPointsRef.current;
    const color = saveForm.color;

    if (pts.length > 0) {
      // Draw segment from last point
      const line = new fabric.Line(
        [pts[pts.length - 1].x, pts[pts.length - 1].y, pointer.x, pointer.y],
        { stroke: color, strokeWidth: 2, selectable: false, evented: false }
      );
      fc.add(line);
      tempObjectsRef.current.push(line);
    } else {
      // First point dot
      const dot = new fabric.Circle({
        left: pointer.x - 4,
        top: pointer.y - 4,
        radius: 4,
        fill: color,
        selectable: false,
        evented: false,
      });
      fc.add(dot);
      tempObjectsRef.current.push(dot);
    }
    pts.push(pointer);

    // Running label
    updateLengthLabel(fc, pts);
    fc.renderAll();
  }

  function updateLengthLabel(fc: fabric.Canvas, pts: { x: number; y: number }[]) {
    // Remove old label
    const existing = tempObjectsRef.current.find(
      (o) => (o as fabric.Object & { _isLabel?: boolean })._isLabel
    );
    if (existing) {
      fc.remove(existing);
      tempObjectsRef.current = tempObjectsRef.current.filter((o) => o !== existing);
    }
    if (pts.length < 2) return;
    const rawPx = polylineLength(pts);
    const { value, unit } = formatValue(rawPx, "length", calibrationRef.current);
    const midX = (pts[0].x + pts[pts.length - 1].x) / 2;
    const midY = (pts[0].y + pts[pts.length - 1].y) / 2 - 14;
    const label = new fabric.Text(`${value.toFixed(2)} ${unit}`, {
      left: midX,
      top: midY,
      fontSize: 12,
      fill: "#091426",
      backgroundColor: "rgba(255,255,255,0.8)",
      selectable: false,
      evented: false,
    }) as fabric.Object & { _isLabel?: boolean };
    label._isLabel = true;
    fc.add(label);
    tempObjectsRef.current.push(label);
  }

  function finishLength(fc: fabric.Canvas) {
    const pts = [...drawingPointsRef.current];
    if (pts.length < 2) { cancelDrawing(); return; }
    const rawPx = polylineLength(pts);
    const { value, unit } = formatValue(rawPx, "length", calibrationRef.current);
    // Clear temp objects
    tempObjectsRef.current.forEach((o) => fc.remove(o));
    tempObjectsRef.current = [];
    drawingPointsRef.current = [];

    // Draw permanent polyline
    const color = saveForm.color;
    for (let i = 0; i < pts.length - 1; i++) {
      const seg = new fabric.Line([pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y], {
        stroke: color,
        strokeWidth: 2,
        selectable: false,
        evented: false,
      });
      fc.add(seg);
    }
    // Endpoint dots
    [pts[0], pts[pts.length - 1]].forEach((p) => {
      fc.add(new fabric.Circle({ left: p.x - 4, top: p.y - 4, radius: 4, fill: color, selectable: false, evented: false }));
    });
    // Label
    const midX = (pts[0].x + pts[pts.length - 1].x) / 2;
    const midY = (pts[0].y + pts[pts.length - 1].y) / 2 - 14;
    fc.add(new fabric.Text(`${value.toFixed(2)} ${unit}`, {
      left: midX, top: midY, fontSize: 12, fill: "#091426",
      backgroundColor: "rgba(255,255,255,0.85)", selectable: false, evented: false,
    }));
    fc.renderAll();

    const newPending: PendingMeasurement = { type: "length", points: pts, rawValue: rawPx, unit };
    setPending(newPending);
    setSaveForm((f) => ({ ...f, label: `Length ${measurements.length + 1}` }));
  }

  // ── Area tool ───────────────────────────────────────────────────────────────
  function handleAreaClick(pointer: { x: number; y: number }, fc: fabric.Canvas) {
    const pts = drawingPointsRef.current;
    const color = saveForm.color;

    if (pts.length > 0) {
      const line = new fabric.Line(
        [pts[pts.length - 1].x, pts[pts.length - 1].y, pointer.x, pointer.y],
        { stroke: color, strokeWidth: 2, selectable: false, evented: false }
      );
      fc.add(line);
      tempObjectsRef.current.push(line);
    } else {
      const dot = new fabric.Circle({
        left: pointer.x - 4, top: pointer.y - 4, radius: 4,
        fill: color, selectable: false, evented: false,
      });
      fc.add(dot);
      tempObjectsRef.current.push(dot);
    }
    pts.push(pointer);
    updateAreaLabel(fc, pts);
    fc.renderAll();
  }

  function updateAreaLabel(fc: fabric.Canvas, pts: { x: number; y: number }[]) {
    const existing = tempObjectsRef.current.find(
      (o) => (o as fabric.Object & { _isLabel?: boolean })._isLabel
    );
    if (existing) {
      fc.remove(existing);
      tempObjectsRef.current = tempObjectsRef.current.filter((o) => o !== existing);
    }
    if (pts.length < 3) return;
    const rawPx = polygonArea(pts);
    const { value, unit } = formatValue(rawPx, "area", calibrationRef.current);
    const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    const label = new fabric.Text(`${value.toFixed(2)} ${unit}`, {
      left: cx, top: cy, fontSize: 12, fill: "#091426",
      backgroundColor: "rgba(255,255,255,0.8)", selectable: false, evented: false,
    }) as fabric.Object & { _isLabel?: boolean };
    label._isLabel = true;
    fc.add(label);
    tempObjectsRef.current.push(label);
  }

  function finishArea(fc: fabric.Canvas) {
    const pts = [...drawingPointsRef.current];
    if (pts.length < 3) { cancelDrawing(); return; }
    const rawPx = polygonArea(pts);
    const { value, unit } = formatValue(rawPx, "area", calibrationRef.current);
    tempObjectsRef.current.forEach((o) => fc.remove(o));
    tempObjectsRef.current = [];
    drawingPointsRef.current = [];

    const color = saveForm.color;
    // Filled polygon
    const fabricPts = pts.map((p) => ({ x: p.x, y: p.y }));
    const poly = new fabric.Polygon(fabricPts, {
      fill: color + "33", // 20% opacity
      stroke: color,
      strokeWidth: 2,
      selectable: false,
      evented: false,
    });
    fc.add(poly);
    // Label
    const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    fc.add(new fabric.Text(`${value.toFixed(2)} ${unit}`, {
      left: cx, top: cy, fontSize: 12, fill: "#091426",
      backgroundColor: "rgba(255,255,255,0.85)", selectable: false, evented: false,
    }));
    fc.renderAll();

    const newPending: PendingMeasurement = { type: "area", points: pts, rawValue: rawPx, unit };
    setPending(newPending);
    setSaveForm((f) => ({ ...f, label: `Area ${measurements.length + 1}` }));
  }

  // ── Count tool ──────────────────────────────────────────────────────────────
  function handleCountClick(pointer: { x: number; y: number }, fc: fabric.Canvas) {
    const color = saveForm.color;
    countRef.current += 1;
    const n = countRef.current;
    const circle = new fabric.Circle({
      left: pointer.x - 10, top: pointer.y - 10, radius: 10,
      fill: color + "cc", stroke: color, strokeWidth: 1.5,
      selectable: false, evented: false,
    });
    const text = new fabric.Text(String(n), {
      left: pointer.x - (n >= 10 ? 7 : 4), top: pointer.y - 8,
      fontSize: 11, fill: "#fff", fontWeight: "bold",
      selectable: false, evented: false,
    });
    fc.add(circle, text);
    tempObjectsRef.current.push(circle, text);

    const pts = drawingPointsRef.current;
    pts.push(pointer);

    const newPending: PendingMeasurement = {
      type: "count",
      points: [...pts],
      rawValue: pts.length,
      unit: "Nr",
    };
    setPending(newPending);
    setSaveForm((f) => ({ ...f, label: `Count ${measurements.length + 1}` }));
    fc.renderAll();
  }

  // ── Save measurement ────────────────────────────────────────────────────────
  async function saveMeasurement() {
    if (!pending) return;
    setSaving(true);
    try {
      const typeMap = { length: "LENGTH", area: "AREA", count: "COUNT" } as const;
      const { data } = await api.post(
        `/projects/${projectId}/drawings/${drawingId}/measurements`,
        {
          page_number: pageNumber,
          label: saveForm.label || `${pending.type} measurement`,
          measurement_type: typeMap[pending.type],
          discipline: saveForm.discipline,
          section: saveForm.section,
          element_category: saveForm.elementCategory || "GENERAL",
          points_json: { points: pending.points },
          multiplier: saveForm.multiplier,
          color: saveForm.color,
          project_element_id: saveForm.project_element_id || null,
        }
      );
      setMeasurements((m) => [...m, data]);
      setPending(null);
      setSaveForm(DEFAULT_FORM);
      tempObjectsRef.current = [];
      drawingPointsRef.current = [];
      countRef.current = 0;
      showToast("Measurement saved");
    } catch {
      showToast("Failed to save measurement", "error");
    } finally {
      setSaving(false);
    }
  }

  function discardPending() {
    cancelDrawing();
    countRef.current = 0;
    setSaveForm(DEFAULT_FORM);
  }

  // ── Delete measurement ──────────────────────────────────────────────────────
  async function deleteMeasurement(id: string) {
    try {
      await api.delete(`/projects/${projectId}/measurements/${id}`);
      setMeasurements((m) => m.filter((x) => x.id !== id));
      showToast("Measurement deleted");
    } catch {
      showToast("Failed to delete", "error");
    }
  }

  // ── Promote to BOQ ──────────────────────────────────────────────────────────
  async function promoteToBoq(id: string) {
    try {
      await api.post(`/projects/${projectId}/measurements/${id}/create-quantity`, {});
      showToast("Added to BOQ queue");
    } catch {
      showToast("Failed to promote", "error");
    }
  }

  // ── Zoom controls ───────────────────────────────────────────────────────────
  function zoomIn() {
    const fc = fabricRef.current;
    if (!fc) return;
    const z = Math.min(fc.getZoom() * 1.2, 10);
    fc.setZoom(z);
    setZoom(Math.round(z * 100) / 100);
  }

  function zoomOut() {
    const fc = fabricRef.current;
    if (!fc) return;
    const z = Math.max(fc.getZoom() / 1.2, 0.1);
    fc.setZoom(z);
    setZoom(Math.round(z * 100) / 100);
  }

  function fitToScreen() {
    const fc = fabricRef.current;
    const container = containerRef.current;
    if (!fc || !container || !pdfDims.width) return;
    const scaleX = container.clientWidth / pdfDims.width;
    const scaleY = container.clientHeight / pdfDims.height;
    const z = Math.min(scaleX, scaleY, 1);
    fc.setZoom(z);
    fc.absolutePan(new fabric.Point(0, 0));
    setZoom(Math.round(z * 100) / 100);
  }

  // ── Tool selector ───────────────────────────────────────────────────────────
  function selectTool(t: Tool) {
    if (t !== activeTool) cancelDrawing();
    setActiveTool(t);
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const calibStatus = calibration
    ? `1px = ${(calibration.scale_factor * 1000).toFixed(3)} mm`
    : "Not calibrated";

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#f7f9fb]">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#091426] text-white shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm truncate max-w-xs">{drawingName}</span>
          {!calibration && (
            <span className="text-xs bg-yellow-500 text-black px-2 py-0.5 rounded-full font-medium">
              Not calibrated — values in pixels
            </span>
          )}
        </div>
        <button onClick={onClose} className="p-1.5 hover:bg-white/10 rounded" aria-label="Close">
          <X size={18} />
        </button>
      </div>

      {/* ── Body ── */}
      <div className="flex flex-1 min-h-0">
        {/* ── Left toolbar ── */}
        <div className="w-12 bg-white border-r border-gray-200 flex flex-col items-center py-3 gap-1 shrink-0">
          {(
            [
              { tool: "select" as Tool, icon: <MousePointer2 size={18} />, label: "Select / Pan" },
              { tool: "calibrate" as Tool, icon: <Ruler size={18} />, label: "Calibrate" },
              { tool: "length" as Tool, icon: <Minus size={18} />, label: "Length" },
              { tool: "area" as Tool, icon: <Square size={18} />, label: "Area" },
              { tool: "count" as Tool, icon: <Hash size={18} />, label: "Count" },
            ] as { tool: Tool; icon: React.ReactNode; label: string }[]
          ).map(({ tool, icon, label }) => (
            <button
              key={tool}
              title={label}
              onClick={() => selectTool(tool)}
              className={`w-9 h-9 flex items-center justify-center rounded transition-colors
                ${activeTool === tool
                  ? "bg-[#eb6905] text-white"
                  : "text-gray-500 hover:bg-gray-100"
                }`}
              aria-label={label}
            >
              {icon}
            </button>
          ))}

          <div className="w-6 border-t border-gray-200 my-1" />

          <button title="Zoom in" onClick={zoomIn} className="w-9 h-9 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100" aria-label="Zoom in">
            <ZoomIn size={18} />
          </button>
          <button title="Zoom out" onClick={zoomOut} className="w-9 h-9 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100" aria-label="Zoom out">
            <ZoomOut size={18} />
          </button>
          <button title="Fit to screen" onClick={fitToScreen} className="w-9 h-9 flex items-center justify-center rounded text-gray-500 hover:bg-gray-100" aria-label="Fit to screen">
            <Maximize2 size={18} />
          </button>
        </div>

        {/* ── Canvas area ── */}
        <div ref={containerRef} className="flex-1 overflow-hidden relative bg-gray-300">
          {/* PDF canvas (hidden, used as source) */}
          <canvas ref={pdfCanvasRef} className="hidden" />
          {/* Fabric canvas */}
          <canvas ref={fabricCanvasRef} />
        </div>

        {/* ── Right panel ── */}
        <div className="w-72 bg-white border-l border-gray-200 flex flex-col shrink-0 overflow-y-auto">
          {/* Drawing info */}
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Drawing</p>
            <p className="text-sm font-medium text-gray-800 truncate">{drawingName}</p>
            <p className="text-xs text-gray-500 mt-0.5">Page {pageNumber}</p>
          </div>

          {/* Calibration status */}
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">Calibration</p>
            {calibration ? (
              <div className="space-y-0.5">
                <p className="text-xs text-green-700 font-medium">✓ Calibrated</p>
                <p className="text-xs text-gray-600">
                  Scale: {(calibration.scale_factor * 1000).toFixed(3)} mm/px
                </p>
                <p className="text-xs text-gray-600">
                  {calibration.pixels_per_meter.toFixed(1)} px/m
                </p>
                {calibration.floor_level && (
                  <p className="text-xs text-gray-500">Floor: {calibration.floor_level}</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-yellow-600">
                Not calibrated — use the Calibrate tool to set scale
              </p>
            )}
          </div>

          {/* Save form (when pending) */}
          {pending && (
            <div className="px-4 py-3 border-b border-gray-100 bg-orange-50">
              <p className="text-xs font-semibold text-[#eb6905] uppercase tracking-wide mb-2">
                Save Measurement
              </p>
              <div className="space-y-2">
                <div>
                  <label className="text-xs text-gray-500 block mb-0.5">Label</label>
                  <input
                    className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-[#eb6905]"
                    value={saveForm.label}
                    onChange={(e) => setSaveForm((f) => ({ ...f, label: e.target.value }))}
                    placeholder="Measurement label"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-0.5">Discipline</label>
                  <select
                    className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-[#eb6905]"
                    value={saveForm.discipline}
                    onChange={(e) => setSaveForm((f) => ({ ...f, discipline: e.target.value as Discipline }))}
                  >
                    {DISCIPLINES.map((d) => <option key={d}>{d}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-0.5">Section</label>
                  <select
                    className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-[#eb6905]"
                    value={saveForm.section}
                    onChange={(e) => setSaveForm((f) => ({ ...f, section: e.target.value as Section }))}
                  >
                    {SECTIONS.map((s) => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-0.5">Link to Element</label>
                  <select
                    className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-[#eb6905]"
                    value={saveForm.project_element_id}
                    onChange={(e) => {
                      const elId = e.target.value;
                      const el = elements.find(x => x.id === elId);
                      setSaveForm((f) => ({
                        ...f,
                        project_element_id: elId,
                        elementCategory: el ? el.element_type : f.elementCategory,
                        discipline: el ? el.discipline as Discipline : f.discipline,
                        section: el ? el.section as Section : f.section,
                      }));
                    }}
                  >
                    <option value="">— Optional —</option>
                    {elements.map((el) => (
                      <option key={el.id} value={el.id}>
                        {el.element_code} ({el.element_type})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-0.5">Element Category</label>
                  <input
                    className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-[#eb6905]"
                    value={saveForm.elementCategory}
                    onChange={(e) => setSaveForm((f) => ({ ...f, elementCategory: e.target.value }))}
                    placeholder="e.g. COLUMN, BEAM, WALL"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-0.5">Multiplier</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.01"
                    className="w-full border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:border-[#eb6905]"
                    value={saveForm.multiplier}
                    onChange={(e) => setSaveForm((f) => ({ ...f, multiplier: parseFloat(e.target.value) || 1 }))}
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">Color</label>
                  <div className="flex gap-1.5">
                    {PRESET_COLORS.map((c) => (
                      <button
                        key={c}
                        onClick={() => setSaveForm((f) => ({ ...f, color: c }))}
                        className={`w-6 h-6 rounded-full border-2 transition-transform ${saveForm.color === c ? "border-gray-800 scale-110" : "border-transparent"}`}
                        style={{ backgroundColor: c }}
                        aria-label={`Color ${c}`}
                      />
                    ))}
                  </div>
                </div>
                {/* Value preview */}
                <div className="bg-white rounded p-2 border border-gray-200">
                  <p className="text-xs text-gray-500">Value</p>
                  <p className="text-sm font-semibold text-gray-800">
                    {formatValue(pending.rawValue, pending.type, calibration).value.toFixed(3)}{" "}
                    {formatValue(pending.rawValue, pending.type, calibration).unit}
                    {saveForm.multiplier !== 1 && (
                      <span className="text-gray-400 text-xs ml-1">× {saveForm.multiplier}</span>
                    )}
                  </p>
                </div>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={saveMeasurement}
                    disabled={saving}
                    className="flex-1 bg-[#eb6905] text-white text-sm py-1.5 rounded font-medium hover:bg-orange-600 disabled:opacity-50 flex items-center justify-center gap-1"
                  >
                    <Check size={14} /> {saving ? "Saving…" : "Save"}
                  </button>
                  <button
                    onClick={discardPending}
                    className="flex-1 border border-gray-200 text-gray-600 text-sm py-1.5 rounded hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Measurements list */}
          <div className="flex-1 px-4 py-3">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Measurements ({measurements.length})
            </p>
            {measurements.length === 0 ? (
              <p className="text-xs text-gray-400 italic">No measurements yet</p>
            ) : (
              <div className="space-y-2">
                {measurements.map((m) => (
                  <div key={m.id} className="border border-gray-100 rounded-lg p-2.5 bg-gray-50">
                    <div className="flex items-start justify-between gap-1">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: m.color }}
                        />
                        <span className="text-xs font-medium text-gray-800 truncate">{m.label}</span>
                      </div>
                      <span className="text-[10px] bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded shrink-0">
                        {m.measurement_type}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-gray-800 mt-1">
                      {m.final_value.toFixed(3)} {m.unit}
                    </p>
                    <p className="text-[10px] text-gray-400">{m.discipline} · {m.section}</p>
                    <div className="flex gap-1.5 mt-2">
                      <button
                        onClick={() => promoteToBoq(m.id)}
                        className="flex items-center gap-1 text-[10px] bg-[#091426] text-white px-2 py-1 rounded hover:bg-[#1e293b]"
                        title="Promote to BOQ"
                      >
                        <ArrowRight size={10} /> BOQ
                      </button>
                      <button
                        onClick={() => deleteMeasurement(m.id)}
                        className="flex items-center gap-1 text-[10px] text-red-500 border border-red-200 px-2 py-1 rounded hover:bg-red-50"
                        title="Delete measurement"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Bottom status bar ── */}
      <div className="flex items-center gap-4 px-4 py-1.5 bg-[#091426] text-white text-xs shrink-0">
        <span>X: {coords.x} Y: {coords.y}</span>
        <span className="text-gray-400">|</span>
        <span>Zoom: {Math.round(zoom * 100)}%</span>
        <span className="text-gray-400">|</span>
        <span className={calibration ? "text-green-400" : "text-yellow-400"}>{calibStatus}</span>
        <span className="text-gray-400">|</span>
        <span className="capitalize">{activeTool}</span>
        {activeTool === "length" && drawingPointsRef.current.length > 0 && (
          <span className="text-gray-400">— double-click to finish</span>
        )}
        {activeTool === "area" && drawingPointsRef.current.length > 0 && (
          <span className="text-gray-400">— double-click to close polygon</span>
        )}
      </div>

      {/* ── Calibration modal ── */}
      {showCalibModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-80">
            <h3 className="text-base font-semibold text-gray-800 mb-4">Enter Real Distance</h3>
            <p className="text-sm text-gray-500 mb-4">
              What is the real-world distance between the two points you selected?
            </p>
            <div className="flex gap-2 mb-4">
              <input
                type="number"
                step="any"
                min="0"
                className="flex-1 border border-gray-200 rounded px-3 py-2 text-sm focus:outline-none focus:border-[#eb6905]"
                placeholder="Distance"
                value={calibDistance}
                onChange={(e) => setCalibDistance(e.target.value)}
                autoFocus
                onKeyDown={(e) => { if (e.key === "Enter") confirmCalibration(); }}
              />
              <select
                className="border border-gray-200 rounded px-2 py-2 text-sm focus:outline-none focus:border-[#eb6905]"
                value={calibUnit}
                onChange={(e) => setCalibUnit(e.target.value as "m" | "mm" | "cm")}
              >
                <option value="mm">mm</option>
                <option value="cm">cm</option>
                <option value="m">m</option>
              </select>
            </div>
            <div className="flex gap-2">
              <button
                onClick={confirmCalibration}
                className="flex-1 bg-[#eb6905] text-white py-2 rounded font-medium hover:bg-orange-600 text-sm"
              >
                Confirm
              </button>
              <button
                onClick={cancelCalibration}
                className="flex-1 border border-gray-200 text-gray-600 py-2 rounded hover:bg-gray-50 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Toasts ── */}
      <div className="fixed bottom-10 left-1/2 -translate-x-1/2 flex flex-col gap-2 z-70 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-2 rounded-lg shadow-lg text-sm font-medium text-white transition-all
              ${t.type === "success" ? "bg-green-600" : "bg-red-600"}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
