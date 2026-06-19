"use client";
import { useMemo, useState, useEffect, useRef } from 'react';
import { StatCard } from '@/components/stat-card';
import { useBotsQuery, useIdentitiesQuery, useProceduresQuery, useDocumentsQuery, useSocialAccountsQuery, useMajorTopicsQuery, useHeatmapQuery } from '@/lib/queries';
import type { Bot, Identity, Procedure, KnowledgeDocument, SocialAccount } from '@/lib/api';
import type { TopicItem, HeatmapItem } from '@/lib/api';

export default function DashboardPage() {
  const botsQuery = useBotsQuery();
  const identitiesQuery = useIdentitiesQuery();
  const proceduresQuery = useProceduresQuery();
  const documentsQuery = useDocumentsQuery();
  const accountsQuery = useSocialAccountsQuery('s_facebook');
  const topicsQuery = useMajorTopicsQuery({ limit: 12 });
  const heatmapQuery = useHeatmapQuery();

  const bots: Bot[] = (botsQuery.data as Bot[]) || [];
  const identities: Identity[] = (identitiesQuery.data as Identity[]) || [];
  const procedures: Procedure[] = (proceduresQuery.data as Procedure[]) || [];
  const documents: KnowledgeDocument[] = (documentsQuery.data as KnowledgeDocument[]) || [];
  const accounts: SocialAccount[] = (accountsQuery.data as SocialAccount[]) || [];
  const topicsData: TopicItem[] = (topicsQuery.data as TopicItem[]) || [];
  const heatmapData: HeatmapItem[] = (heatmapQuery.data as HeatmapItem[]) || [];

  const [hoverCell, setHoverCell] = useState<{ dow: number; hour: number; count: number; x: number; y: number } | null>(null);
  const heatmapRef = useRef<HTMLDivElement | null>(null);
  const cellRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const [autoIndex, setAutoIndex] = useState<number>(0);
  const [paused, setPaused] = useState<boolean>(false);

  const [autoTopicIdx, setAutoTopicIdx] = useState<number>(0);
  const [pausedTopicAuto, setPausedTopicAuto] = useState<boolean>(false);

  const botsTotal = bots.length;
  const botsActive = useMemo(() => bots.filter((b) => (b.status || '').toLowerCase() === 'active').length, [bots]);
  const socialTotal = accounts.length;
  const knowledgeTotal = documents.length;
  const identitiesTotal = identities.length;
  const workflowTotal = procedures.length;

  const getColors = (n: number) => {
    const palette = ["#2563eb","#16a34a","#f59e0b","#ef4444","#8b5cf6","#0ea5e9","#22c55e","#db2777"];
    return palette.slice(0, Math.max(1, Math.min(n, palette.length)));
  };

  const topicSlices = useMemo(() => {
    const rows = topicsData;
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
  }, [topicsData]);

  useEffect(() => {
    setAutoTopicIdx(0);
  }, [topicsData]);

  useEffect(() => {
    const active = topicSlices.filter((s) => s.count > 0);
    if (pausedTopicAuto || active.length === 0) return;
    const id = setTimeout(() => setAutoTopicIdx((i) => (i + 1) % active.length), 1600);
    return () => clearTimeout(id);
  }, [topicSlices, autoTopicIdx, pausedTopicAuto]);

  useEffect(() => {
    const active = heatmapData
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
  }, [heatmapData, autoIndex, paused]);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Trang Chủ</h1>
      <p className="text-gray-500 mb-8">Real-time insights into your AI sales and customer engagement</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Bots" total={botsTotal} active={botsActive} percentage={0} />
        <StatCard title="Identities" total={identitiesTotal} percentage={0} />
        <StatCard title="Workflow" total={workflowTotal} percentage={0} />
        <StatCard title="Social Accounts" total={socialTotal} percentage={0} />
        <StatCard title="Knowledge" total={knowledgeTotal} percentage={0} />
        <StatCard title="Chats" total={0} percentage={0} />
        <StatCard title="Feedback" total={0} percentage={0} />
      </div>

      <div className="grid grid-cols-1 gap-6 mt-8">
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold">Chủ đề phổ biến theo ngành</h2>
          </div>
          <div className="h-64 flex items-center justify-center">
            {Array.isArray(topicsData) && topicsData.length > 0 ? (
              <div className="flex items-center gap-4" onMouseEnter={() => setPausedTopicAuto(true)} onMouseLeave={() => setPausedTopicAuto(false)}>
                <div
                  className="relative w-56 h-56 rounded-full"
                  style={{ background: (() => {
                    const rows = topicsData;
                    const total = rows.reduce((s, r) => s + r.count, 0) || 1;
                    let acc = 0;
                    const stops: string[] = [];
                    const palette = getColors(rows.length || 5);
                    rows.forEach((r, i) => {
                      const start = (acc / total) * 100;
                      acc += r.count;
                      const end = (acc / total) * 100;
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
                <div className="w-56 bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-2 text-[12px] text-gray-700">
                  {(() => {
                    const rows = topicsData;
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
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">Không có dữ liệu</div>
            )}
          </div>
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
                <div className="w-8 text-[10px] text-gray-500 text-right pr-1">{["T2","T3","T4","T5","T6","T7","CN"][d]}</div>
                <div className="flex-1 grid grid-cols-24 gap-1">
                  {Array.from({ length: 24 }).map((_, h) => {
                    const cell = heatmapData.find((c) => c.dow === d && c.hour === h);
                    const k = cell ? cell.count : 0;
                    const max = Math.max(1, ...heatmapData.map((c) => c.count));
                    const ratio = Math.min(1, k / max);
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
                {["T2","T3","T4","T5","T6","T7","CN"][hoverCell.dow]} • {hoverCell.hour}h · {hoverCell.count} lượt/giờ
              </div>
            )}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-2 w-40 rounded" style={{ background: "linear-gradient(to right, rgba(37, 99, 235, 0.15), rgba(37, 99, 235, 1))" }} />
            <div className="text-[11px] text-gray-600">0 → {Math.max(0, ...heatmapData.map((c) => c.count))} lượt hỏi/giờ</div>
          </div>
        </div>
      </div>
    </div>
  );
}
