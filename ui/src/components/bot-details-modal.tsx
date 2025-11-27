"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { X, Eye, Rocket, FileText, Globe, Languages, BadgeCheck, Trash2 } from "lucide-react";
import type { Bot, KnowledgeDocument } from "@/lib/api";
import { getBotKnowledge, getSocialPageById, removeBotKnowledge } from "@/lib/api";
import { EditBotModal } from "@/components/edit-bot-modal";

interface BotDetailsModalProps {
  bot: Bot | null;
  open: boolean;
  onClose: () => void;
}

export function BotDetailsModal({ bot, open, onClose }: BotDetailsModalProps) {
  const [editOpen, setEditOpen] = useState(false);
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>([]);
  const [connectedPages, setConnectedPages] = useState<Array<{ id: string | number; name: string }>>([]);

  const bullets = (text?: string) => {
    if (!text) return [] as string[];
    return text
      .split(/\r?\n/) // split by lines
      .map(s => s.trim())
      .filter(Boolean);
  };

  const missionLines = bullets(bot?.mission);
  const roleLines = bullets(bot?.role);
  const targetLines = bullets(bot?.target);

  useEffect(() => {
    if (!open || !bot) return;
    const run = async () => {
      try {
        const k = await getBotKnowledge(bot.id);
        const docs = Array.isArray((k as any)?.data?.documents) ? (k as any).data.documents : [];
        setKnowledgeDocs(docs as any);
      } catch {}
      try {
        const con = bot.connect;
        let items: any[] = [];
        if (Array.isArray(con)) items = con;
        else if (typeof con === "string") {
          try {
            const parsed = JSON.parse(con);
            if (Array.isArray(parsed)) items = parsed;
          } catch {}
        }
        const list: Array<{ id: string | number; name: string }> = [];
        const tasks: Array<Promise<any>> = [];
        const keys: Array<string | number> = [];
        for (const it of items) {
          if (it?.social_id === "s_facebook" && (it?.fb_page_id || it?.social_page_id)) {
            const pid = it?.fb_page_id || it?.social_page_id;
            keys.push(pid);
            tasks.push(getSocialPageById("s_facebook", pid));
          }
        }
        if (tasks.length) {
          const results = await Promise.all(tasks.map((t) => t.catch(() => null)));
          for (let i = 0; i < results.length; i++) {
            const r = results[i];
            const data = r?.data || {};
            list.push({ id: keys[i], name: data?.fb_page_name || data?.name || items[i]?.fb_page_name || String(keys[i]) });
          }
        }
        setConnectedPages(list);
      } catch {}
    };
    run();
  }, [open, bot?.id]);

  if (!open || !bot) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div
          className="relative w-full max-w-4xl bg-white rounded-xl border shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between p-6 border-b">
            <div>
              <h2 className="text-xl font-semibold">{bot.name}</h2>
              <p className="mt-2 text-gray-600">
                {(roleLines.length === 0 ? bot.role : roleLines[0]) || "Chưa có mô tả vai trò"}
              </p>
            </div>
            <Button variant="outline" size="icon" className="bg-white" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* Identity & Workflow */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="text-sm font-medium text-gray-500">Danh tính</div>
                <div className="rounded-lg border p-4">
                  <div className="text-sm text-gray-800 break-words">{bot.name}</div>
                  {bot.type && (
                    <div className="mt-2 text-xs text-gray-500">Loại: {bot.type}</div>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium text-gray-500">Quy trình</div>
                <div className="rounded-lg border p-4">
                  <div className="text-sm text-gray-800">{(bot as any).workflow || "Chưa cấu hình"}</div>
                </div>
              </div>
            </div>

            {/* Role */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Vai trò</div>
              <div className="rounded-lg border p-4 space-y-2">
                {roleLines.length > 1 ? (
                  <ul className="list-disc pl-5 text-sm text-gray-800 space-y-1">
                    {roleLines.map((line, i) => (
                      <li key={`role-${i}`}>{line}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm text-gray-800 break-words">{bot.role || "Chưa có"}</div>
                )}
              </div>
            </div>

            {/* Target / Goal */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Mục tiêu</div>
              <div className="rounded-lg border p-4 space-y-2">
                {targetLines.length > 1 ? (
                  <ul className="list-disc pl-5 text-sm text-gray-800 space-y-1">
                    {targetLines.map((line, i) => (
                      <li key={`target-${i}`}>{line}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm text-gray-800 break-words">{bot.target || "Chưa có"}</div>
                )}
              </div>
            </div>

            {/* Mission / Tasks */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Nhiệm vụ</div>
              <div className="rounded-lg border p-4 space-y-2">
                {missionLines.length > 1 ? (
                  <ul className="list-disc pl-5 text-sm text-gray-800 space-y-1">
                    {missionLines.map((line, i) => (
                      <li key={`mission-${i}`}>{line}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm text-gray-800 break-words">{bot.mission || "Chưa có"}</div>
                )}
              </div>
            </div>

            {/* Note */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Ghi chú</div>
              <div className="rounded-lg border p-4">
                <div className="text-sm text-gray-800 break-words">{bot.note || "Không có ghi chú"}</div>
              </div>
            </div>

            {/* Meta */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="space-y-2">
                <div className="text-sm font-medium text-gray-500">Trạng thái</div>
                <div className="rounded-lg border p-4 text-sm text-gray-800">
                  {bot.status || "Không xác định"}
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium text-gray-500">Loại</div>
                <div className="rounded-lg border p-4 text-sm text-gray-800">
                  {bot.type || "Không xác định"}
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium text-gray-500">Ngôn ngữ</div>
                <div className="rounded-lg border p-4 text-sm text-gray-800">
                  {(bot as any).language || "Không thiết lập"}
                </div>
              </div>
            </div>

            {/* Knowledge Docs */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Tài liệu kiến thức</div>
              <div className="rounded-lg border p-4">
                {knowledgeDocs.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {knowledgeDocs.map((d, i) => (
                      <span key={`doc-${i}`} className="inline-flex items-center gap-2 rounded-full border px-3 py-1 bg-gray-50 text-sm text-gray-800">
                        <FileText className="w-3.5 h-3.5" /> {d.title || String(d.id)}
                        <button className="ml-1 text-red-600" onClick={async () => { try { await removeBotKnowledge(bot.id, d.id); const k = await getBotKnowledge(bot.id); const docs = Array.isArray((k as any)?.data?.documents) ? (k as any).data.documents : []; setKnowledgeDocs(docs as any); } catch {} }}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-800">Chưa có tài liệu kiến thức nào được chỉ định.</div>
                )}
              </div>
            </div>

            {/* Connected pages */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-gray-500">Kết nối trang</div>
              <div className="rounded-lg border p-4">
                {connectedPages.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {connectedPages.map((p, i) => (
                      <span key={`page-${i}`} className="inline-flex items-center gap-2 rounded-full border px-3 py-1 bg-gray-50 text-sm text-gray-800">
                        <Globe className="w-3.5 h-3.5" /> {p.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-800">Chưa có trang được kết nối.</div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="outline" className="bg-white" onClick={() => setEditOpen(true)}>Chỉnh sửa cấu hình</Button>
              <Button className="bg-blue-600 hover:bg-blue-700 text-white flex items-center gap-2">
                <Rocket className="h-4 w-4" />
                Kiểm tra & Triển khai
              </Button>
            </div>
          </div>
        </div>
        <EditBotModal open={editOpen} onClose={() => setEditOpen(false)} bot={bot} onUpdated={() => {}} />
      </div>
    </div>
  );
}