"use client";

import { useState, useMemo, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, AlertCircle } from "lucide-react";
import {
  useTopMajorsQuery,
  useMajorsTimelineQuery,
  useMajorTopicsQuery,
  usePopularQuestionsQuery,
  useHeatmapQuery,
} from "@/lib/queries";
import { getAccessToken } from "@/lib/auth-storage";
import type {
  MajorTopItem,
  MajorsTimelineItem,
  TopicItem,
  PopularQuestionItem,
  HeatmapItem,
} from "@/lib/api";

type Color = string;

function useColors(n: number): Color[] {
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
  const timeline = useMajorsTimelineQuery(params, enabled);
  const topics = useMajorTopicsQuery({ ...params, major: selectedMajor || undefined }, enabled);
  const questions = usePopularQuestionsQuery({ ...params, limit: 20 }, enabled);
  const heatmap = useHeatmapQuery(params, enabled);

  const topData: MajorTopItem[] = useMemo(() => (Array.isArray(topMajors.data) ? (topMajors.data as MajorTopItem[]) : []), [topMajors.data]);
  const majorsForSelect = topData.map((x) => x.major);
  const colors = useColors(majorsForSelect.length || 5);

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
    const LEFT_PAD = 20;
    const RIGHT_PAD = 10;
    const CHART_H = 220;
    const LABEL_H = 100;
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
      const y = CHART_H - h;
      const hasValue = c > 0;
      const color = hasValue ? colors[i % colors.length] : "#e5e7eb";
      const label = majors[i];
      const cx = x + BAR_W / 2;
      const cy = y;
      return { x, y, w: BAR_W, h, color, label, value: c, cx, cy, hasValue };
    });
    const svgH = CHART_H + LABEL_H;
    const points = rects.map((r) => `${r.cx},${r.cy}`);
    return { rects, svgW, svgH, points };
  }, [DEFAULT_MAJORS, topData, colors, barAlign]);

  const pieStyle = useMemo(() => {
    const rows: Array<{ major: string; count: number }> = Array.isArray(topMajors.data) ? (topMajors.data as Array<{ major: string; count: number }>) : [];
    const total = rows.reduce((s, r) => s + r.count, 0) || 1;
    let acc = 0;
    const stops: string[] = [];
    rows.forEach((r, i) => {
      const start = (acc / total) * 100;
      acc += r.count;
      const end = (acc / total) * 100;
      const color = colors[i % colors.length];
      stops.push(`${color} ${start}% ${end}%`);
    });
    const bg = `conic-gradient(${stops.join(", ")})`;
    return { background: bg } as React.CSSProperties;
  }, [topMajors.data, colors]);

  const timelineSeries = useMemo(() => {
    const rows: MajorsTimelineItem[] = Array.isArray(timeline.data) ? (timeline.data as MajorsTimelineItem[]) : [];
    const majors = majorsForSelect.length > 0 ? majorsForSelect.slice(0, 5) : [];
    const dates = rows.map((r) => r.date);
    const max = rows.reduce((m, r) => Math.max(m, ...Object.values(r.counts || {})), 0) || 1;
    const pointsByMajor: Record<string, Array<{ x: number; y: number }>> = {};
    majors.forEach((maj) => {
      pointsByMajor[maj] = rows.map((r, idx) => ({ x: idx, y: (r.counts?.[maj] ?? 0) / max }));
    });
    return { majors, pointsByMajor, dates };
  }, [timeline.data, majorsForSelect]);

  const heatMeta = useMemo(() => {
    const cells: HeatmapItem[] = Array.isArray(heatmap.data) ? (heatmap.data as HeatmapItem[]) : [];
    const max = cells.reduce((m, c) => Math.max(m, c.count), 0) || 1;
    return { cells, max };
  }, [heatmap.data]);

  const loading = topMajors.isLoading || timeline.isLoading || topics.isLoading || questions.isLoading || heatmap.isLoading;
  const errorMsg = (() => {
    const err: unknown = topMajors.error ?? timeline.error ?? topics.error ?? questions.error ?? heatmap.error;
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
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
        <div>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black mb-2">Thống kê tuyển sinh</h1>
          <p className="text-gray-600">Phân tích ngành được hỏi nhiều nhất</p>
        </div>
        <div className="flex gap-2 items-end">
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-40 border-gray-300" />
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-40 border-gray-300" />
          <Select value={limit} onValueChange={setLimit}>
            <SelectTrigger className="w-28 border-gray-300">
              <SelectValue placeholder="Top" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="5">Top 5</SelectItem>
              <SelectItem value="10">Top 10</SelectItem>
              <SelectItem value="20">Top 20</SelectItem>
            </SelectContent>
          </Select>
          <Button className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white">Lọc</Button>
        </div>
      </div>

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
                    >
                      {columnLine.rects.map((r, idx) => (
                        <g key={`bar-${idx}`}>
                          <rect x={r.x} y={r.y} width={r.w} height={r.h} rx={6} fill={r.color} />

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

                          {/* FIX LABEL ROTATE & OVERFLOW */}
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

                      {/* Line above bars */}
                      <polyline
                        points={columnLine.points.join(" ")}
                        fill="none"
                        stroke="#2563eb"
                        strokeWidth={2}
                      />

                      {columnLine.rects.map((r, idx) => (
                        <circle
                          key={`pt-${idx}`}
                          cx={r.cx}
                          cy={r.cy}
                          r={r.hasValue ? 3 : 2}
                          fill={r.hasValue ? "#2563eb" : "#60a5fa"}
                        />
                      ))}
                    </svg>
                  ) : (
                    <div className="h-full flex items-center justify-center text-gray-500">
                      Không có dữ liệu
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Xu hướng theo thời gian</h2>
            </div>
            <div className="h-64 relative">
              {timelineSeries.majors.length > 0 ? (
                <svg viewBox="0 0 600 240" className="w-full h-full">
                  {timelineSeries.majors.map((maj, i) => {
                    const pts = timelineSeries.pointsByMajor[maj].map((p) => `${(p.x / Math.max(1, timelineSeries.dates.length - 1)) * 580 + 10},${240 - p.y * 220}`);
                    const color = colors[i % colors.length];
                    return <polyline key={maj} points={pts.join(" ")} fill="none" stroke={color} strokeWidth={2} />;
                  })}
                </svg>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
            {timelineSeries.majors.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-3 items-center">
                {timelineSeries.majors.map((maj, i) => (
                  <div key={`lg-tl-${maj}-${i}`} className="flex items-center gap-2">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: colors[i % colors.length] }} />
                    <span className="text-sm text-gray-600">{maj}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Tỷ lệ phân bổ ngành</h2>
            </div>
            <div className="h-64 flex items-center justify-center">
              {Array.isArray(topMajors.data) && topMajors.data.length > 0 ? (
                <div className="relative w-48 h-48 rounded-full" style={pieStyle}>
                  <div className="absolute inset-4 bg-white rounded-full"></div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
            {Array.isArray(topMajors.data) && topMajors.data.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-3 justify-center">
                {(topMajors.data as { major: string; count: number }[]).map((r, i) => (
                  <div key={`lg-pie-${r.major}-${i}`} className="flex items-center gap-2">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: colors[i % colors.length] }} />
                    <span className="text-sm text-gray-600">{r.major}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Chủ đề phổ biến theo ngành</h2>
              <Select value={selectedMajor} onValueChange={setSelectedMajor}>
                <SelectTrigger className="w-48 border-gray-300">
                  <SelectValue placeholder="Chọn ngành" />
                </SelectTrigger>
                <SelectContent>
                  {majorsForSelect.map((m) => (
                    <SelectItem value={m} key={m}>{m}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="h-64 flex items-center justify-center">
              {Array.isArray(topics.data) && topics.data.length > 0 ? (
                <div className="relative w-48 h-48 rounded-full" style={{ background: (() => {
                  const rows: TopicItem[] = Array.isArray(topics.data) ? (topics.data as TopicItem[]) : [];
                  const total = rows.reduce((s, r) => s + r.count, 0) || 1;
                  let acc = 0;
                  const stops: string[] = [];
                  rows.forEach((r, i) => {
                    const start = (acc / total) * 100;
                    acc += r.count;
                    const end = (acc / total) * 100;
                    const color = colors[i % colors.length];
                    stops.push(`${color} ${start}% ${end}%`);
                  });
                  return `conic-gradient(${stops.join(", ")})`;
                })() }}>
                  <div className="absolute inset-4 bg-white rounded-full"></div>
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
            {Array.isArray(topics.data) && topics.data.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-3 justify-center">
                {(topics.data as TopicItem[]).map((t, i) => (
                  <div key={`lg-topic-${t.topic}-${i}`} className="flex items-center gap-2">
                    <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: colors[i % colors.length] }} />
                    <span className="text-sm text-gray-600">{t.topic}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Top câu hỏi lặp lại</h2>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {Array.isArray(questions.data) && questions.data.length > 0 ? (
                (questions.data as PopularQuestionItem[]).map((q: PopularQuestionItem, idx: number) => (
                  <div key={`${q.question}-${idx}`} className="flex items-start justify-between">
                    <div className="flex-1 pr-4">
                      <div className="text-sm text-gray-900">{q.question || q.sample}</div>
                      <div className="text-xs text-gray-500">{q.sample}</div>
                    </div>
                    <div className="text-xs font-semibold text-gray-700">{q.count}</div>
                  </div>
                ))
              ) : (
                <div className="h-32 flex items-center justify-center text-gray-500">Không có dữ liệu</div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Thời điểm hỏi nhiều nhất</h2>
            </div>
            <div className="grid grid-cols-24 gap-1">
              <div className="col-span-24 grid grid-cols-24 gap-1">
                {Array.from({ length: 24 }).map((_, h) => (
                  <div key={`h-${h}`} className="text-[10px] text-gray-500 text-center">{h}</div>
                ))}
              </div>
              {Array.from({ length: 7 }).map((_, d) => {
                return (
                  <div key={`d-${d}`} className="col-span-24 grid grid-cols-24 gap-1">
                    {Array.from({ length: 24 }).map((_, h) => {
                      const cell = heatMeta.cells.find((c) => c.dow === d && c.hour === h);
                      const k = cell ? cell.count : 0;
                      const ratio = Math.min(1, k / Math.max(1, heatMeta.max));
                      const bg = `rgba(37, 99, 235, ${0.15 + ratio * 0.85})`;
                      return <div key={`c-${d}-${h}`} className="h-4 rounded" style={{ backgroundColor: bg }} />;
                    })}
                  </div>
                );
              })}
            </div>
        </div>
        </div>
        </div>
      )}
    </div>
  );
}
