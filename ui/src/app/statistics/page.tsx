"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, AlertCircle } from "lucide-react";
import {
  useTopMajorsQuery,
  useMajorTopicsQuery,
  usePopularQuestionsQuery,
  useHeatmapQuery,
} from "@/lib/queries";
import { getAccessToken } from "@/lib/auth-storage";
import type { 
  MajorTopItem,
  TopicItem,
  PopularQuestionItem,
  HeatmapItem,
} from "@/lib/api";

type Color = string;

function getColors(n: number): Color[] {
  const palette = [
    "#2563eb",
    "#16a34a",
    "#f59e0b",
    "#ef4444",
    "#8b5cf6",
    "#0ea5e9",
    "#22c55e",
    "#db2777",
  ];
  return palette.slice(0, Math.max(1, Math.min(n, palette.length)));
}

function toISO(d?: string) {
  if (!d) return undefined;
  try {
    const t = new Date(d);
    if (Number.isNaN(t.getTime())) return undefined;
    const y = t.getFullYear();
    const m = String(t.getMonth() + 1).padStart(2, "0");
    const day = String(t.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  } catch {
    return undefined;
  }
}

export default function StatisticsPage() {
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [selectedMajor, setSelectedMajor] = useState<string>("");
  const [limit, setLimit] = useState<string>("10");
  const [hydrated, setHydrated] = useState<boolean>(false);
  const [enabled, setEnabled] = useState<boolean>(false);
  const [barAlign, setBarAlign] = useState<"left" | "right" | "center">("center");

  const params: {
    start_date?: string;
    end_date?: string;
    limit?: number;
    session_id?: string;
    customer_id?: string;
    bot_id?: string;
    social_id?: string;
    social_page_id?: string;
    auto_extract?: boolean;
  } = {
    start_date: toISO(startDate),
    end_date: toISO(endDate),
    limit: Number(limit) || 10,
    auto_extract: true,
  };

  useEffect(() => {
    const id = setTimeout(() => {
      setHydrated(true);
      setEnabled(!!getAccessToken());
    }, 0);
    return () => clearTimeout(id);
  }, []);

  const topMajors = useTopMajorsQuery(params, enabled);
  const topics = useMajorTopicsQuery({ ...params, major: selectedMajor || undefined }, enabled);
  const questions = usePopularQuestionsQuery({ ...params, limit: 20 }, enabled);
  const heatmap = useHeatmapQuery(params, enabled);

  const topData: MajorTopItem[] = useMemo(() => (Array.isArray(topMajors.data) ? (topMajors.data as MajorTopItem[]) : []), [topMajors.data]);
  const majorsForSelect = topData.map((x) => x.major);

  const DEFAULT_MAJORS = useMemo(
    () => [
      "Marketing",
      "Quản trị kinh doanh",
      "Quản trị nhân lực",
      "Kinh doanh thương mại",
      "Thương mại điện tử",
      "Logistics và Quản lý chuỗi cung ứng",
      "Kinh tế quốc tế",
      "Kinh tế",
      "Song ngành Kinh tế - Tài chính",
      "Kế toán",
      "Kiểm toán",
      "Tài chính - Ngân hàng",
      "Kinh tế nông nghiệp",
      "Kinh tế chính trị (Miễn học phí)",
      "Hệ thống thông tin quản lý",
      "Thống kê kinh tế",
      "Kinh tế số",
    ],
    []
  );

  const presentMajors = useMemo(() => DEFAULT_MAJORS.filter((m) => topData.some((d) => d.major === m)), [DEFAULT_MAJORS, topData]);

  const columnLine = useMemo(() => {
    const BAR_W = 20;
    const GAP = 50;
    const LEFT_PAD = 24;
    const RIGHT_PAD = 10;
    const CHART_H = 200;
    const LABEL_H = 100;
    const TOP_PAD = 16;
    const majors = DEFAULT_MAJORS;
    const counts = majors.map((m) => topData.find((d) => d.major === m)?.count ?? 0);
    const localMax = Math.max(1, ...counts);
    const n = counts.length;
    const svgW = LEFT_PAD + RIGHT_PAD + 2 * GAP + n * (BAR_W + GAP);
    const rects = counts.map((c, i) => {
      const h = c > 0 ? Math.round((c / localMax) * CHART_H) : 2;
      const step = BAR_W + GAP;
      const contentStart = LEFT_PAD + GAP;
      const contentEnd = svgW - RIGHT_PAD - GAP;
      const contentWidth = Math.max(0, contentEnd - contentStart);
      const barsWidth = Math.max(0, n * BAR_W + (n - 1) * GAP);
      const centerOffset = Math.max(0, Math.floor((contentWidth - barsWidth) / 2));
      const x = barAlign === "right"
        ? contentEnd - BAR_W - i * step
        : barAlign === "left"
        ? contentStart + i * step
        : contentStart + centerOffset + i * step;
      const y = TOP_PAD + CHART_H - h;
      const hasValue = c > 0;
      const color = hasValue ? "#2563eb" : "#e5e7eb";
      const label = majors[i];
      const cx = x + BAR_W / 2;
      const cy = y;
      return { x, y, w: BAR_W, h, color, label, value: c, cx, cy, hasValue };
    });
    const svgH = TOP_PAD + CHART_H + LABEL_H;
    const contentStart = LEFT_PAD + GAP;
    const contentEnd = svgW - RIGHT_PAD - GAP;
    const tickVals = localMax <= 5
      ? Array.from({ length: localMax + 1 }, (_, i) => i)
      : (() => {
          const base = Math.ceil(localMax / 4);
          const candidates = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000];
          const step = candidates.find((c) => c >= base) ?? base;
          const vals: number[] = [];
          for (let v = 0; v <= localMax; v += step) vals.push(v);
          if (vals[vals.length - 1] !== localMax) vals.push(localMax);
          return vals;
        })();
    const ticks = tickVals.map((val) => ({ val, y: TOP_PAD + CHART_H - (val / localMax) * CHART_H }));
    return { rects, svgW, svgH, max: localMax, chartH: CHART_H, contentStart, contentEnd, ticks, topPad: TOP_PAD };
  }, [DEFAULT_MAJORS, topData, barAlign]);

  const percentDist = useMemo(() => {
    const rows: Array<{ major: string; count: number }> = Array.isArray(topMajors.data) ? (topMajors.data as Array<{ major: string; count: number }>) : [];
    const total = rows.reduce((s, r) => s + r.count, 0) || 1;
    const items = rows
      .map((r) => ({
        major: r.major,
        count: r.count,
        pct: Math.round(((r.count / total) * 100) * 10) / 10,
      }))
      .sort((a, b) => b.count - a.count);
    const PAD_L = 180;
    const PAD_R = 40;
    const PAD_T = 24;
    const ROW_H = 30;
    const BAR_H = 18;
    const n = items.length;
    const svgW = 900;
    const svgH = PAD_T + n * ROW_H + 40;
    const barMaxW = svgW - PAD_L - PAD_R;
    const rects = items.map((it, idx) => {
      const y = PAD_T + idx * ROW_H;
      const w = Math.max(2, Math.round((it.pct / 100) * barMaxW));
      return { x: PAD_L, y, w, h: BAR_H, label: it.major, pct: it.pct };
    });
    const xTicks = [0, 25, 50, 75, 100].map((p) => ({ x: PAD_L + (p / 100) * barMaxW, label: p }));
    return { rects, svgW, svgH, xTicks };
  }, [topMajors.data]);

  const [hoverBarIdx, setHoverBarIdx] = useState<number | null>(null);
  const [showTopicPct, setShowTopicPct] = useState<boolean>(true);
  const [hoverCell, setHoverCell] = useState<{ dow: number; hour: number; count: number; x: number; y: number } | null>(null);
  const [autoTopicIdx, setAutoTopicIdx] = useState<number>(0);
  const [pausedTopicAuto, setPausedTopicAuto] = useState<boolean>(false);
  const [autoBarIdx, setAutoBarIdx] = useState<number>(0);
  const [pausedBars, setPausedBars] = useState<boolean>(false);
  const [autoPctIdx, setAutoPctIdx] = useState<number>(0);
  const [pausedPct, setPausedPct] = useState<boolean>(false);
  const [autoQIdx, setAutoQIdx] = useState<number>(0);
  const [pausedQ, setPausedQ] = useState<boolean>(false);

  const heatMeta = useMemo(() => {
    const cells: HeatmapItem[] = Array.isArray(heatmap.data) ? (heatmap.data as HeatmapItem[]) : [];
    const max = cells.reduce((m, c) => Math.max(m, c.count), 0) || 1;
    return { cells, max };
  }, [heatmap.data]);
  const dowLabels = useMemo(() => ["T2", "T3", "T4", "T5", "T6", "T7", "CN"], []);
  const heatmapRef = useRef<HTMLDivElement | null>(null);
  const cellRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [autoIndex, setAutoIndex] = useState<number>(0);
  const [paused, setPaused] = useState<boolean>(false);
  const questionsRef = useRef<HTMLDivElement | null>(null);
  const questionRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    const active = heatMeta.cells
      .filter((c) => c.count > 0)
      .sort((a, b) => (a.dow - b.dow) || (a.hour - b.hour));
    if (paused || active.length === 0) return;
    const c = active[autoIndex % active.length];
    const el = cellRefs.current[`${c.dow}-${c.hour}`];
    const cr = heatmapRef.current?.getBoundingClientRect();
    const r = el?.getBoundingClientRect();
    const x = r && cr ? r.left - cr.left + r.width / 2 : 0;
    const y = r && cr ? r.top - cr.top + r.height / 2 : 0;
    setHoverCell({ dow: c.dow, hour: c.hour, count: c.count, x, y });
    const id = setTimeout(() => setAutoIndex((i) => (i + 1) % active.length), 1400);
    return () => clearTimeout(id);
  }, [heatMeta.cells, autoIndex, paused]);

  useEffect(() => {
    setAutoBarIdx(0);
  }, [columnLine.rects]);

  useEffect(() => {
    const n = columnLine.rects.length;
    if (pausedBars || n === 0) return;
    const id = setTimeout(() => setAutoBarIdx((i) => (i + 1) % n), 1500);
    return () => clearTimeout(id);
  }, [columnLine.rects, autoBarIdx, pausedBars]);

  const topicSlices = useMemo(() => {
    const rows: TopicItem[] = Array.isArray(topics.data) ? (topics.data as TopicItem[]) : [];
    const total = rows.reduce((s, r) => s + r.count, 0) || 1;
    const palette = getColors(rows.length || 5);
    let acc = 0;
    return rows.map((r, i) => {
      const start = (acc / total) * 100;
      acc += r.count;
      const end = (acc / total) * 100;
      const pct = Math.round(((r.count / total) * 100) * 10) / 10;
      const color = palette[i % palette.length];
      return { start, end, color, topic: r.topic, pct, count: r.count };
    });
  }, [topics.data]);

  useEffect(() => {
    setAutoTopicIdx(0);
  }, [selectedMajor, topics.data]);

  useEffect(() => {
    const active = topicSlices.filter((s) => s.count > 0);
    if (pausedTopicAuto || active.length === 0) return;
    const id = setTimeout(() => setAutoTopicIdx((i) => (i + 1) % active.length), 1600);
    return () => clearTimeout(id);
  }, [topicSlices, autoTopicIdx, pausedTopicAuto]);

  useEffect(() => {
    setAutoPctIdx(0);
  }, [percentDist.rects]);

  useEffect(() => {
    const activeIdxs = percentDist.rects.map((r, i) => ({ i, w: r.w })).filter((x) => x.w > 2);
    if (pausedPct || activeIdxs.length === 0) return;
    const id = setTimeout(() => {
      setAutoPctIdx((cur) => {
        const currentI = activeIdxs.findIndex((x) => x.i === cur);
        if (currentI < 0) return activeIdxs[0].i;
        const next = activeIdxs[(currentI + 1) % activeIdxs.length].i;
        return next;
      });
    }, 1500);
    return () => clearTimeout(id);
  }, [percentDist.rects, autoPctIdx, pausedPct]);
  
  useEffect(() => {
    setAutoQIdx(0);
  }, [questions.data]);
  
  useEffect(() => {
    const items: PopularQuestionItem[] = Array.isArray(questions.data) ? (questions.data as PopularQuestionItem[]) : [];
    if (pausedQ || items.length === 0) return;
    const idx = autoQIdx % items.length;
    const id = setTimeout(() => setAutoQIdx((i) => (i + 1) % items.length), 1600);
    return () => clearTimeout(id);
  }, [questions.data, autoQIdx, pausedQ]);

  const loading = topMajors.isLoading || topics.isLoading || questions.isLoading || heatmap.isLoading;
  const errorMsg = (() => {
    const err: unknown = topMajors.error ?? topics.error ?? questions.error ?? heatmap.error;
    if (!err) return "";
    if (typeof err === "string") return err;
    if (typeof err === "object" && err && "message" in err) {
      const m = (err as { message?: string }).message;
      return m || "Lỗi tải dữ liệu";
    }
    return "Lỗi tải dữ liệu";
  })();

  return (
    <div className="min-h-screen p-6">

      {!hydrated ? (
        <div className="flex flex-col justify-center items-center py-20">
          <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
          <span className="text-gray-600 font-medium">Đang tải thống kê...</span>
        </div>
      ) : loading ? (
        <div className="flex flex-col justify-center items-center py-20">
          <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
          <span className="text-gray-600 font-medium">Đang tải thống kê...</span>
        </div>
      ) : errorMsg ? (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-red-700 font-medium">{errorMsg}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 xl:grid-cols-1 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">Top ngành được hỏi nhiều nhất</h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Căn</span>
                  <Select value={barAlign} onValueChange={(v) => setBarAlign(v as "left" | "right" | "center")}> 
                    <SelectTrigger className="w-28 border-gray-300">
                      <SelectValue placeholder="Căn" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem className="text-black" value="left">Căn trái</SelectItem>
                      <SelectItem className="text-black" value="center">Căn giữa</SelectItem>
                      <SelectItem className="text-black" value="right">Căn phải</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Scrollable wrapper: FIX CROP ISSUE */}
              <div
                className="overflow-x-hidden overflow-y-visible"
                style={{ paddingBottom: "60px", paddingLeft: barAlign === "right" ? 0 : barAlign === "left" ? "40px" : "40px", paddingRight: barAlign === "right" ? "40px" : barAlign === "left" ? 0 : "40px" }}
              >
                <div style={{ minWidth: columnLine.svgW, display: "flex", justifyContent: barAlign === "right" ? "flex-end" : barAlign === "left" ? "flex-start" : "center" }}>
                  {presentMajors.length > 0 ? (
                    <svg
                      width="100%"
                      height={columnLine.svgH + 160}
                      viewBox={`0 0 ${columnLine.svgW} ${columnLine.svgH + 170}`}
                      preserveAspectRatio={barAlign === "right" ? "xMaxYMin meet" : barAlign === "left" ? "xMinYMin meet" : "xMidYMin meet"}
                      className="block"
                      onMouseEnter={() => setPausedBars(true)}
                      onMouseLeave={() => setPausedBars(false)}
                    >
                      <line x1={columnLine.contentStart} y1={columnLine.topPad} x2={columnLine.contentStart} y2={columnLine.topPad + columnLine.chartH} stroke="#e5e7eb" strokeWidth={1} />
                      {columnLine.ticks.map((t, i) => (
                        <g key={`y-grid-${i}`}>
                          <line x1={columnLine.contentStart} y1={t.y} x2={columnLine.contentEnd} y2={t.y} stroke="#f3f4f6" strokeWidth={1} />
                          <text x={columnLine.contentStart - 8} y={t.y + 4} textAnchor="end" fontSize="11" fill="#6b7280">
                            {t.val}
                          </text>
                        </g>
                      ))}
                      {(() => {
                        const pts = columnLine.rects.map((r) => `${r.cx},${r.y}`).join(" ");
                        return (
                          <>
                            <polyline points={pts} fill="none" stroke="#60a5fa" strokeWidth={2} />
                            {columnLine.rects.map((r, i) => {
                              const active = i === autoBarIdx;
                              return <circle key={`pt-${i}`} cx={r.cx} cy={r.y} r={active ? 5 : 3} fill={active ? "#2563eb" : "#93c5fd"} />;
                            })}
                          </>
                        );
                      })()}
                      {columnLine.rects.map((r, idx) => (
                        <g key={`bar-${idx}`}>
                          <rect x={r.x} y={r.y} width={r.w} height={r.h} rx={6} fill={r.color} stroke={autoBarIdx === idx ? "#2563eb" : "none"} strokeWidth={autoBarIdx === idx ? 2 : 0} />

                          {r.hasValue && (
                            <text
                              x={r.x + r.w / 2}
                              y={Math.max(14, r.y - 6)}
                              textAnchor="middle"
                              fontSize="11"
                              fill="#374151"
                            >
                              {r.value}
                            </text>
                          )}

                          <text
                            transform={`rotate(-45 ${r.x + r.w / 2} ${columnLine.svgH + 20})`}
                            x={r.x + r.w / 2}
                            y={columnLine.svgH + 20}
                            textAnchor="end"
                            fontSize="13"
                            fill="#4b5563"
                          >
                            {r.label}
                          </text>
                        </g>
                      ))}

                    </svg>
                  ) : (
                    <div className="h-full flex items-center justify-center text-gray-500">
                      Không có dữ liệu
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: "#2563eb" }} />
                <span className="text-sm text-gray-600">Số lượt câu hỏi</span>
              </div>
              <div className="mt-2 text-xs text-gray-500">
                <span className="font-medium">Nguồn dữ liệu:</span> Log chatbot Facebook Messenger.{" "}
                <span className="font-medium">Thời gian:</span>{" "}
                {(() => {
                  const fmt = (d: string) => {
                    if (!d) return "";
                    const t = new Date(d);
                    if (Number.isNaN(t.getTime())) return "";
                    const dd = String(t.getDate()).padStart(2, "0");
                    const mm = String(t.getMonth() + 1).padStart(2, "0");
                    const yy = t.getFullYear();
                    return `${dd}/${mm}/${yy}`;
                  };
                  const s = fmt(startDate);
                  const e = fmt(endDate);
                  if (s && e) return `${s} – ${e}`;
                  if (s && !e) return `${s} – hiện tại`;
                  if (!s && e) return `đến ${e}`;
                  return "Không giới hạn";
                })()}
              </div>
              {Array.isArray(topData) && topData.length > 0 && (
                <div className="mt-3 bg-blue-50 border border-blue-100 rounded-lg p-3">
                  <div className="text-sm text-blue-900">
                    {(() => {
                      const rows = [...topData].sort((a, b) => b.count - a.count);
                      const top3 = rows.slice(0, 3).map((r) => r.major);
                      const zeroCnt = DEFAULT_MAJORS.filter((m) => !(topData as MajorTopItem[]).some((d) => d.major === m)).length;
                      return `Biểu đồ cho thấy mức độ quan tâm không đồng đều. Các ngành nổi bật gồm ${top3.join(", ")} có số lượt hỏi cao hơn đáng kể. Đồng thời, nhiều ngành gần như không phát sinh câu hỏi trong giai đoạn khảo sát (≈ ${zeroCnt} ngành).`;
                    })()}
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Tỷ lệ phân bổ ngành</h2>
            </div>
            <div className="h-[420px] relative">
              {Array.isArray(topMajors.data) && topMajors.data.length > 0 ? (
                <svg
                  width="100%"
                  height={percentDist.svgH}
                  viewBox={`0 0 ${percentDist.svgW} ${percentDist.svgH}`}
                  className="w-full h-full"
                  onMouseEnter={() => setPausedPct(true)}
                  onMouseLeave={() => setPausedPct(false)}
                >
                  {percentDist.xTicks.map((t, i) => (
                    <g key={`px-${i}`}>
                      <line x1={t.x} y1={12} x2={t.x} y2={percentDist.svgH - 24} stroke="#f3f4f6" strokeWidth={1} />
                      <text x={t.x} y={percentDist.svgH - 8} textAnchor="middle" fontSize="11" fill="#6b7280">
                        {t.label}%
                      </text>
                    </g>
                  ))}
                  {percentDist.rects.map((r, i) => {
                    const selectedIdx = pausedPct ? hoverBarIdx : autoPctIdx;
                    const active = selectedIdx === i;
                    return (
                    <g
                      key={`pct-bar-${i}`}
                      onMouseEnter={() => setHoverBarIdx(i)}
                      onMouseLeave={() => setHoverBarIdx(null)}
                      cursor="pointer"
                    >
                      <text x={r.x - 10} y={r.y + r.h - 2} textAnchor="end" fontSize="12" fill="#374151">
                        {r.label}
                      </text>
                      <rect x={r.x} y={r.y} width={r.w} height={r.h} rx={4} fill={active ? "#1d4ed8" : "#2563eb"} stroke={active ? "#1d4ed8" : "none"} strokeWidth={active ? 2 : 0} />
                      {active && (
                        <g>
                          <rect x={r.x + r.w + 8} y={r.y - 4} width={50} height={r.h + 8} rx={6} fill="#ffffff" stroke="#2563eb" />
                          <text x={r.x + r.w + 33} y={r.y + r.h / 2 + 4} textAnchor="middle" fontSize="12" fill="#2563eb">
                            {r.pct}%
                          </text>
                        </g>
                      )}
                    </g>
                  );
                  })}
                </svg>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Chủ đề phổ biến theo ngành</h2>
              <Select value={selectedMajor} onValueChange={(v) => setSelectedMajor(v === "__ALL__" ? "" : v)}>
                <SelectTrigger className="w-48 border-gray-300">
                  <SelectValue placeholder="Chọn ngành hoặc Tất cả" />
                </SelectTrigger>
                <SelectContent className="text-black">
                  <SelectItem  value="__ALL__">Tất cả ngành</SelectItem>
                  {majorsForSelect.map((m) => (
                    <SelectItem value={m} key={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="h-64 flex items-center justify-center">
              {Array.isArray(topics.data) && topics.data.length > 0 ? (
                <div
                  className="flex items-center gap-4"
                  onMouseEnter={() => setPausedTopicAuto(true)}
                  onMouseLeave={() => setPausedTopicAuto(false)}
                >
                  <div
                    className="relative w-56 h-56 rounded-full"
                    style={{ background: (() => {
                      const rows: TopicItem[] = Array.isArray(topics.data) ? (topics.data as TopicItem[]) : [];
                      const total = rows.reduce((s, r) => s + r.count, 0) || 1;
                      let acc = 0;
                      const stops: string[] = [];
                      rows.forEach((r, i) => {
                        const start = (acc / total) * 100;
                        acc += r.count;
                        const end = (acc / total) * 100;
                        const palette = getColors(rows.length || 5);
                        const color = palette[i % palette.length];
                        stops.push(`${color} ${start}% ${end}%`);
                      });
                      return `conic-gradient(${stops.join(", ")})`;
                    })() }}
                  >
                    {(() => {
                      const active = topicSlices.filter((s) => s.count > 0);
                      const current = active.length > 0 ? active[autoTopicIdx % active.length] : null;
                      if (!current) return null;
                      return (
                        <div
                          className="absolute inset-0 rounded-full"
                          style={{ background: `conic-gradient(${current.color} ${current.start}% ${current.end}%, transparent ${current.end}% 100%)` }}
                        />
                      );
                    })()}
                    <div className="absolute inset-6 bg-white rounded-full"></div>
                    {(() => {
                      const active = topicSlices.filter((s) => s.count > 0);
                      const current = active.length > 0 ? active[autoTopicIdx % active.length] : null;
                      if (!current) return null;
                      return (
                        <div className="absolute inset-6 rounded-full flex items-center justify-center">
                          <div className="flex items-center gap-2 text-[12px] text-gray-700">
                            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: current.color }} />
                            <span className="font-medium">{current.pct}%</span>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                  {showTopicPct && (
                    <div className="w-56 overflow-y-hidden bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-2 text-[12px] text-gray-700">
                      {(() => {
                        const rows: TopicItem[] = Array.isArray(topics.data) ? (topics.data as TopicItem[]) : [];
                        const total = rows.reduce((s, r) => s + r.count, 0) || 1;
                        const palette = getColors(rows.length || 5);
                        const active = topicSlices.filter((s) => s.count > 0);
                        const current = active.length > 0 ? active[autoTopicIdx % active.length] : null;
                        return rows.map((r, i) => {
                          const pct = Math.round(((r.count / total) * 100) * 10) / 10;
                          const color = palette[i % palette.length];
                           const isActive = !!current && current.topic === r.topic;
                          return (
                            <div key={`pct-topic-${r.topic}-${i}`} className={`flex items-center justify-between gap-2 rounded ${isActive ? "bg-blue-50" : ""}`}>
                              <span className="flex items-center gap-2">
                                <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: color }} />
                                <span className="max-w-[130px] truncate">{r.topic}</span>
                              </span>
                              <span className="font-medium">{pct}%</span>
                            </div>
                          );
                        });
                      })()}
                    </div>
                  )}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
            {Array.isArray(topics.data) && topics.data.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-3 justify-center">
                {(topics.data as TopicItem[]).map((t, i) => (
                  <div key={`lg-topic-${t.topic}-${i}`} className="flex items-center gap-2">
                    <span
                      className="inline-block w-3 h-3 rounded-sm"
                      style={{
                        backgroundColor: getColors(((topics.data as TopicItem[]).length || 5))[i % getColors(((topics.data as TopicItem[]).length || 5)).length],
                      }}
                    />
                    <span className="text-sm text-gray-600">{t.topic}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Thời điểm hỏi nhiều nhất</h2>
            </div>
            <div className="relative space-y-1" ref={heatmapRef} onMouseEnter={() => setPaused(true)} onMouseLeave={() => { setPaused(false); setHoverCell(null); }}>
              <div className="flex gap-1">
                <div className="w-8" />
                <div className="flex-1 grid grid-cols-24 gap-1">
                  {Array.from({ length: 24 }).map((_, h) => (
                    <div key={`h-${h}`} className="text-[10px] text-gray-500 text-center">{h}</div>
                  ))}
                </div>
              </div>
              {Array.from({ length: 7 }).map((_, d) => (
                <div key={`d-${d}`} className="flex gap-1">
                  <div className="w-8 text-[10px] text-gray-500 text-right pr-1">{dowLabels[d]}</div>
                  <div className="flex-1 grid grid-cols-24 gap-1">
                    {Array.from({ length: 24 }).map((_, h) => {
                      const cell = heatMeta.cells.find((c) => c.dow === d && c.hour === h);
                      const k = cell ? cell.count : 0;
                      const ratio = Math.min(1, k / Math.max(1, heatMeta.max));
                      const bg = `rgba(37, 99, 235, ${0.15 + ratio * 0.85})`;
                      const isFocus = !!hoverCell && hoverCell.dow === d && hoverCell.hour === h;
                      const isActive = !!hoverCell && (hoverCell.dow === d || hoverCell.hour === h);
                      return (
                        <div
                          key={`c-${d}-${h}`}
                          className={`h-4 rounded ${isFocus ? "ring-2 ring-blue-600" : isActive ? "ring-1 ring-blue-400" : ""}`}
                          style={{ backgroundColor: bg }}
                          onMouseEnter={(e) => {
                            const r = e.currentTarget.getBoundingClientRect();
                            const cr = heatmapRef.current?.getBoundingClientRect();
                            const x = r.left - (cr?.left ?? 0) + r.width / 2;
                            const y = r.top - (cr?.top ?? 0) + r.height / 2;
                            setHoverCell({ dow: d, hour: h, count: k, x, y });
                          }}
                          ref={(el) => { cellRefs.current[`${d}-${h}`] = el; }}
                        />
                      );
                    })}
                  </div>
                </div>
              ))}
              {hoverCell && (
                <div
                  className="absolute z-10 px-2 py-1 bg-white border border-gray-200 rounded shadow text-[11px] text-gray-700 whitespace-nowrap"
                  style={{ left: hoverCell.x + 12, top: hoverCell.y - 24 }}
                >
                  {dowLabels[hoverCell.dow]} • {hoverCell.hour}h · {hoverCell.count} lượt/giờ
                </div>
              )}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-2 w-40 rounded" style={{ background: "linear-gradient(to right, rgba(37, 99, 235, 0.15), rgba(37, 99, 235, 1))" }} />
              <div className="text-[11px] text-gray-600">0 → {heatMeta.max} lượt hỏi/giờ</div>
            </div>
        </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Top câu hỏi lặp lại</h2>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto" onMouseEnter={() => setPausedQ(true)} onMouseLeave={() => setPausedQ(false)} ref={questionsRef}>
              {Array.isArray(questions.data) && questions.data.length > 0 ? (
                (questions.data as PopularQuestionItem[]).map((q: PopularQuestionItem, idx: number) => {
                  const active = (!pausedQ && autoQIdx === idx);
                  return (
                    <div
                      key={`${q.question}-${idx}`}
                      className={`flex items-start justify-between p-2 rounded border ${active ? "bg-blue-50 border-blue-300" : "border-gray-200"}`}
                      onMouseEnter={() => { setPausedQ(true); setAutoQIdx(idx); }}
                      ref={(el) => { questionRefs.current[`q-${idx}`] = el; }}
                    >
                      <div className="flex-1 pr-4">
                        <div className={`text-sm ${active ? "text-blue-900" : "text-gray-900"}`}>{q.question || q.sample}</div>
                        <div className="text-xs text-gray-500">{q.sample}</div>
                      </div>
                      <div className={`text-xs font-semibold ${active ? "text-blue-700" : "text-gray-700"}`}>{q.count}</div>
                    </div>
                  );
                })
              ) : (
                <div className="h-32 flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
