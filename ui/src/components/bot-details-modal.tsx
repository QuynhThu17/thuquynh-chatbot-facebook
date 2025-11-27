"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { X, Rocket, FileText, Globe, Pencil, Loader2, Trash2, AlertCircle } from "lucide-react";
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
  const [loading, setLoading] = useState(true);
  const [deletingDoc, setDeletingDoc] = useState<string | number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bullets = (text?: string) => {
    if (!text) return [] as string[];
    return text
      .split(/\r?\n/)
      .map(s => s.trim())
      .filter(Boolean);
  };

  const missionLines = bullets(bot?.mission);
  const roleLines = bullets(bot?.role);
  const targetLines = bullets(bot?.target);

  useEffect(() => {
    if (!open || !bot) return;
    
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Fetch knowledge documents
        const k = await getBotKnowledge(bot.id);
        const docs = Array.isArray((k as any)?.data?.documents) ? (k as any).data.documents : [];
        setKnowledgeDocs(docs as any);

        // Fetch connected pages
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
            list.push({ 
              id: keys[i], 
              name: data?.fb_page_name || data?.name || items[i]?.fb_page_name || String(keys[i]) 
            });
          }
        }
        setConnectedPages(list);
      } catch (err: any) {
        setError(err?.message || "Không thể tải dữ liệu");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [open, bot?.id]);

  const handleDeleteKnowledge = async (docId: string | number) => {
    if (!bot) return;
    
    setDeletingDoc(docId);
    setError(null);
    
    try {
      await removeBotKnowledge(bot.id, docId);
      const k = await getBotKnowledge(bot.id);
      const docs = Array.isArray((k as any)?.data?.documents) ? (k as any).data.documents : [];
      setKnowledgeDocs(docs as any);
    } catch (err: any) {
      setError(err?.message || "Không thể xóa tài liệu");
    } finally {
      setDeletingDoc(null);
    }
  };

  if (!open || !bot) return null;

  const isActive = String(bot.status || "").toLowerCase() === "active";

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
        <div
          className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl my-8"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between p-6 border-b border-gray-200">
            <div className="flex items-start gap-4 flex-1">
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-md flex-shrink-0 ${
                isActive ? 'bg-gradient-to-br from-green-500 to-green-600' : 'bg-gradient-to-br from-gray-400 to-gray-500'
              }`}>
                {bot.name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">{bot.name}</h2>
                <div className="flex items-center gap-3 mb-3">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                    isActive 
                      ? 'bg-green-100 text-green-700' 
                      : 'bg-gray-100 text-gray-700'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                    {isActive ? 'Đang hoạt động' : 'Không hoạt động'}
                  </span>
                  {bot.type && (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                      {bot.type}
                    </span>
                  )}
                </div>
                <p className="text-gray-600 text-sm leading-relaxed">
                  {(roleLines.length === 0 ? bot.role : roleLines[0]) || "Chưa có mô tả vai trò"}
                </p>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="icon" 
              className="bg-white hover:bg-gray-100 flex-shrink-0 ml-2"
              onClick={onClose}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mx-6 mt-4 bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700 flex-1">{error}</p>
              <button 
                onClick={() => setError(null)}
                className="text-red-500 hover:text-red-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Content */}
          <div className="p-6 space-y-6 max-h-[calc(100vh-280px)] overflow-y-auto">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500 mb-2" />
                <span className="text-sm text-gray-500">Đang tải thông tin...</span>
              </div>
            ) : (
              <>
                {/* Identity & Workflow */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                      </div>
                      <div className="text-sm font-semibold text-gray-700">Danh tính</div>
                    </div>
                    <div className="text-sm text-gray-900 font-medium">{bot.name}</div>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
                        <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                        </svg>
                      </div>
                      <div className="text-sm font-semibold text-gray-700">Quy trình</div>
                    </div>
                    <div className="text-sm text-gray-900">{(bot as any).workflow || "Chưa cấu hình"}</div>
                  </div>
                </div>

                {/* Role */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <h3 className="text-sm font-semibold text-gray-700">Vai trò</h3>
                  </div>
                  <div className="p-4">
                    {roleLines.length > 1 ? (
                      <ul className="space-y-2">
                        {roleLines.map((line, i) => (
                          <li key={`role-${i}`} className="flex items-start gap-2 text-sm text-gray-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 flex-shrink-0"></span>
                            <span className="flex-1">{line}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-700 leading-relaxed">{bot.role || "Chưa có thông tin vai trò"}</p>
                    )}
                  </div>
                </div>

                {/* Target */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <h3 className="text-sm font-semibold text-gray-700">Mục tiêu</h3>
                  </div>
                  <div className="p-4">
                    {targetLines.length > 1 ? (
                      <ul className="space-y-2">
                        {targetLines.map((line, i) => (
                          <li key={`target-${i}`} className="flex items-start gap-2 text-sm text-gray-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 flex-shrink-0"></span>
                            <span className="flex-1">{line}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-700 leading-relaxed">{bot.target || "Chưa có thông tin mục tiêu"}</p>
                    )}
                  </div>
                </div>

                {/* Mission */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <h3 className="text-sm font-semibold text-gray-700">Nhiệm vụ</h3>
                  </div>
                  <div className="p-4">
                    {missionLines.length > 1 ? (
                      <ul className="space-y-2">
                        {missionLines.map((line, i) => (
                          <li key={`mission-${i}`} className="flex items-start gap-2 text-sm text-gray-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 flex-shrink-0"></span>
                            <span className="flex-1">{line}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-700 leading-relaxed">{bot.mission || "Chưa có thông tin nhiệm vụ"}</p>
                    )}
                  </div>
                </div>

                {/* Note */}
                {bot.note && (
                  <div className="bg-amber-50 rounded-lg border border-amber-200 p-4">
                    <div className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      <div className="flex-1">
                        <div className="text-xs font-semibold text-amber-800 mb-1">Ghi chú</div>
                        <p className="text-sm text-amber-900 leading-relaxed">{bot.note}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Language */}
                {(bot as any).language && (
                  <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
                      </svg>
                      <span className="text-sm font-medium text-gray-700">Ngôn ngữ:</span>
                      <span className="text-sm text-gray-900">{(bot as any).language}</span>
                    </div>
                  </div>
                )}

                {/* Knowledge Documents */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-700">Tài liệu kiến thức</h3>
                      <span className="text-xs text-gray-500">{knowledgeDocs.length} tài liệu</span>
                    </div>
                  </div>
                  <div className="p-4">
                    {knowledgeDocs.length > 0 ? (
                      <div className="space-y-2">
                        {knowledgeDocs.map((d, i) => (
                          <div 
                            key={`doc-${i}`} 
                            className="flex items-center justify-between gap-3 p-3 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors"
                          >
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />
                              <span className="text-sm text-gray-900 truncate">{d.title || String(d.id)}</span>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={deletingDoc === d.id}
                              onClick={() => handleDeleteKnowledge(d.id)}
                              className={`
                                flex-shrink-0 h-8 px-2 
                                bg-white border border-gray-300 
                                text-red-600 
                                hover:bg-red-50 hover:text-red-600 hover:border-red-300
                                disabled:opacity-50 disabled:cursor-not-allowed
                              `}
                            >
                              {deletingDoc === d.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-red-600" />
                              ) : (
                                <Trash2 className="w-3.5 h-3.5 text-red-600" />
                              )}
                            </Button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <FileText className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                        <p className="text-sm text-gray-500">Chưa có tài liệu kiến thức nào</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Connected Pages */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-700">Trang đã kết nối</h3>
                      <span className="text-xs text-gray-500">{connectedPages.length} trang</span>
                    </div>
                  </div>
                  <div className="p-4">
                    {connectedPages.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {connectedPages.map((p, i) => (
                          <span 
                            key={`page-${i}`} 
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-blue-50 text-sm text-gray-900"
                          >
                            <Globe className="w-3.5 h-3.5 text-blue-600" />
                            {p.name}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <Globe className="w-10 h-10 text-gray-300 mx-auto mb-2" />
                        <p className="text-sm text-gray-500">Chưa kết nối với trang nào</p>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
            <Button 
              variant="outline" 
              className="bg-white hover:bg-gray-100"
              onClick={() => setEditOpen(true)}
            >
              <Pencil className="h-4 w-4 mr-2" />
              Chỉnh sửa
            </Button>
            <Button 
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
            >
              <Rocket className="h-4 w-4 mr-2" />
              Kiểm tra & Triển khai
            </Button>
          </div>
        </div>

        {/* Edit Modal */}
        <EditBotModal 
          open={editOpen} 
          onClose={() => setEditOpen(false)} 
          bot={bot} 
          onUpdated={() => {}} 
        />
      </div>
    </div>
  );
}