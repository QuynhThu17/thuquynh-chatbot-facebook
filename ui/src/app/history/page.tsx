"use client";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, AlertCircle, Search, MessageSquare, Bell, Reply, Trash2 } from "lucide-react";
import Image from "next/image";
import {
  getHistories,
  getHistorySessions,
  deleteHistorySession,
  getSocialPageById,
  type HistoryRecord,
  type SessionRecord,
  type NotificationItem,
} from "@/lib/api";
import {
  useHistoriesQuery,
  useHistorySessionsQuery,
  useNotificationsQuery,
  useMarkNotificationReadMutation,
  useMarkNotificationUnreadMutation,
  useDeleteNotificationMutation,
} from "@/lib/queries";

type Tab = "histories" | "notifications";

export default function HistoryPage() {
  const [tab, setTab] = useState<Tab>("histories");
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [pageFilter, setPageFilter] = useState<string | undefined>(undefined);
  const [botFilter, setBotFilter] = useState<string | undefined>(undefined);

  const [histories, setHistories] = useState<HistoryRecord[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);

  type ChatMessage = { id: string | number; direction?: string; text?: string; created_at?: string };
  type PageInfo = { fb_page_avatar?: string; fb_page_name?: string; name?: string; title?: string };
  const [activeRecord, setActiveRecord] = useState<HistoryRecord | ChatMessage | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | number | null>(null);
  const [pageInfo, setPageInfo] = useState<PageInfo | null>(null);
  const [autoReply, setAutoReply] = useState<boolean>(true);
  const [sessionFeed, setSessionFeed] = useState<ChatMessage[]>([]);
  const [notifSearch, setNotifSearch] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);

  const formatRelativeTime = (input?: string | number | Date) => {
    if (!input) return "";
    const t = typeof input === "string" || typeof input === "number" ? new Date(input) : input;
    const ms = Date.now() - (t instanceof Date ? t.getTime() : 0);
    if (!isFinite(ms) || ms <= 0) return "Vừa xong";
    const s = Math.floor(ms / 1000);
    if (s < 60) return "Vừa xong";
    const m = Math.floor(s / 60);
    if (m < 60) return `${m} phút trước`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h} giờ trước`;
    const d = Math.floor(h / 24);
    if (d < 30) return `${d} ngày trước`;
    const mo = Math.floor(d / 30);
    if (mo < 12) return `${mo} tháng trước`;
    const y = Math.floor(mo / 12);
    return `${y} năm trước`;
  };

  const historiesQuery = useHistoriesQuery({ social_page_id: pageFilter, bot_id: botFilter, limit: 50 });
  const sessionsQuery = useHistorySessionsQuery();
  const notificationsQuery = useNotificationsQuery();
  const loading = tab === "histories" ? (historiesQuery.isLoading || sessionsQuery.isLoading) : notificationsQuery.isLoading;

  useEffect(() => {
    if (tab === "histories") {
      const rows = historiesQuery.data as HistoryRecord[] | undefined;
      const ses = sessionsQuery.data as SessionRecord[] | undefined;
      if (Array.isArray(rows)) setHistories(rows);
      if (Array.isArray(ses)) setSessions(ses);
      const err = historiesQuery.error as any;
      const err2 = sessionsQuery.error as any;
      if (!error && (err || err2)) setError((err?.message || err2?.message) || "Lỗi tải dữ liệu");
    } else {
      const rows = notificationsQuery.data as NotificationItem[] | undefined;
      if (Array.isArray(rows)) setNotifications(rows);
      const err = notificationsQuery.error as any;
      if (!error && err) setError(err?.message || "Lỗi tải dữ liệu");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, historiesQuery.data, historiesQuery.error, sessionsQuery.data, sessionsQuery.error, notificationsQuery.data, notificationsQuery.error]);

  const openChat = async (record: HistoryRecord) => {
    setActiveRecord(record);
    setActiveSessionId(record?.session_id ?? null);
    setDetailLoading(true);
    setPageInfo(null);
    try {
      const [piRes, mr] = await Promise.all([
        record?.social_page_id ? getSocialPageById("s_facebook", record.social_page_id) : Promise.resolve(null),
        getHistories({ session_id: String(record?.session_id || ""), limit: 100 })
      ]);
      if (piRes) {
        const piData = (piRes as { data?: unknown } | null)?.data as PageInfo | undefined;
        setPageInfo(piData ?? null);
      }
      const raw = (mr?.data || []) as HistoryRecord[];
      const expanded: ChatMessage[] = [];
      for (const it of raw) {
        if (it?.query) expanded.push({ id: `${it.id}_q`, direction: "in", text: it.query, created_at: it?.created_at });
        if (it?.answer) expanded.push({ id: `${it.id}_a`, direction: "out", text: it.answer, created_at: it?.updated_at || it?.created_at });
        if (!it?.query && !it?.answer) expanded.push({ id: it.id, direction: it.direction, text: it.text, created_at: it?.created_at });
      }
      const msgs = expanded.slice().sort((a, b) => {
        const ta = a?.created_at ? new Date(a.created_at).getTime() : 0;
        const tb = b?.created_at ? new Date(b.created_at).getTime() : 0;
        return ta - tb;
      });
      setSessionFeed(msgs);
    } catch {} finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    const loadBySession = async () => {
      if (!activeSessionId) return;
      try {
        setDetailLoading(true);
        const mr = await getHistories({ session_id: String(activeSessionId || ""), limit: 100 });
        const raw = (mr?.data || []) as HistoryRecord[];
        const expanded: ChatMessage[] = [];
        for (const it of raw) {
          if (it?.query) expanded.push({ id: `${it.id}_q`, direction: "in", text: it.query, created_at: it?.created_at });
          if (it?.answer) expanded.push({ id: `${it.id}_a`, direction: "out", text: it.answer, created_at: it?.updated_at || it?.created_at });
          if (!it?.query && !it?.answer) expanded.push({ id: it.id, direction: it.direction, text: it.text, created_at: it?.created_at });
        }
        const msgs = expanded.slice().sort((a, b) => {
          const ta = a?.created_at ? new Date(a.created_at).getTime() : 0;
          const tb = b?.created_at ? new Date(b.created_at).getTime() : 0;
          return ta - tb;
        });
        setSessionFeed(msgs);
        if (!activeRecord && msgs.length > 0) setActiveRecord(msgs[msgs.length - 1]);
      } catch {} finally {
        setDetailLoading(false);
      }
    };
    loadBySession();
  }, [activeSessionId, activeRecord]);

  const markReadMutation = useMarkNotificationReadMutation();
  const markUnreadMutation = useMarkNotificationUnreadMutation();
  const markRead = async (id: string | number, read: boolean) => {
    try {
      if (read) await markReadMutation.mutateAsync(id);
      else await markUnreadMutation.mutateAsync(id);
      setNotifications((prev) => prev.map((n) => (String(n.id) === String(id) ? { ...n, is_read: read } : n)));
    } catch {}
  };

  const removeSession = async (id: string | number) => {
    try {
      await deleteHistorySession(id);
      setSessions((prev) => prev.filter((s) => String(s.id) !== String(id)));
    } catch {}
  };

  const deleteNotifMutation = useDeleteNotificationMutation();
  const removeNotification = async (id: string | number) => {
    try {
      await deleteNotifMutation.mutateAsync(id);
      setNotifications((prev) => prev.filter((n) => String(n.id) !== String(id)));
    } catch {}
  };

  const sessionMessages = sessionFeed;

  

  const conversationCount = new Set(histories.map((h) => String(h.session_id || ""))).size;
  const replyCount = histories.filter((h) => String(h.direction || "") === "out").length;
  const unreadNotificationsCount = notifications.filter((n) => !n?.is_read).length;
  const filteredNotifications = notifications.filter((n) => {
    const text = `${n?.title || ""} ${n?.content || ""}`.toLowerCase();
    const q = notifSearch.trim().toLowerCase();
    if (!q) return true;
    return text.includes(q);
  });

  return (
    <div className="min-h-screen from-slate-50 to-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black mb-2">Lịch sử & Hộp thư</h1>
            <p className="text-gray-600">Quản lý cuộc trò chuyện, phản hồi và thông báo</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">Cuộc trò chuyện</CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <MessageSquare className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{conversationCount}</div>
              <p className="text-xs text-gray-500 mt-1">Phiên hội thoại</p>
            </CardContent>
          </Card>

          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">Phản hồi</CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-md">
                <Reply className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{replyCount}</div>
              <p className="text-xs text-gray-500 mt-1">Tin nhắn trả lời</p>
            </CardContent>
          </Card>

          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">Thông báo</CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-md">
                <Bell className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3">
                <div className="text-3xl font-bold text-gray-900">{notifications.length}</div>
                <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-600">{unreadNotificationsCount} chưa đọc</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
            <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg">
              <button
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  tab === "histories" ? "bg-white text-blue-600 shadow-sm" : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setTab("histories")}
              >
                Cuộc trò chuyện
              </button>
              <button
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  tab === "notifications" ? "bg-white text-blue-600 shadow-sm" : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setTab("notifications")}
              >
                Thông báo
              </button>
            </div>

            {tab === "histories" && (
              <div className="flex items-center gap-3">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    placeholder="Tìm kiếm tin nhắn..."
                    className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                <Select value={botFilter ?? undefined} onValueChange={(v) => setBotFilter(v === "__all__" ? undefined : v)}>
                  <SelectTrigger className="w-full sm:w-[180px] border-gray-300">
                    <SelectValue placeholder="Bot" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">Tất cả bot</SelectItem>
                    {Array.from(new Set(histories.map((h) => String(h.bot_id || ""))).values())
                      .filter((v) => v)
                      .map((v) => (
                        <SelectItem key={v} value={v}>{v}</SelectItem>
                      ))}
                  </SelectContent>
                </Select>

                <Select value={pageFilter ?? undefined} onValueChange={(v) => setPageFilter(v === "__all__" ? undefined : v)}>
                  <SelectTrigger className="w-full sm:w-[180px] border-gray-300">
                    <SelectValue placeholder="Trang" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all__">Tất cả trang</SelectItem>
                    {Array.from(new Set(histories.map((h) => String(h.social_page_id || ""))).values())
                      .filter((v) => v)
                      .map((v) => (
                        <SelectItem key={v} value={v}>{v}</SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {tab === "notifications" && (
              <div className="flex items-center gap-3">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    placeholder="Tìm kiếm thông báo..."
                    className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                    value={notifSearch}
                    onChange={(e) => setNotifSearch(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

      {tab === "histories" && (
        <div>
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center gap-3">
              <div className="relative w-64">
                <Input placeholder="Tìm kiếm..." value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <Select value={pageFilter ?? undefined} onValueChange={(v) => setPageFilter(v === "__all__" ? undefined : v)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Trang" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tất cả trang</SelectItem>
                  {Array.from(new Set(histories.map((h) => String(h.social_page_id || ""))).values())
                    .filter((v) => v)
                    .map((v) => (
                      <SelectItem key={v} value={v}>{v}</SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <Select value={botFilter ?? undefined} onValueChange={(v) => setBotFilter(v === "__all__" ? undefined : v)}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Bot" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Tất cả bot</SelectItem>
                  {Array.from(new Set(histories.map((h) => String(h.bot_id || ""))).values())
                    .filter((v) => v)
                    .map((v) => (
                      <SelectItem key={v} value={v}>{v}</SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {loading && (
            <div className="flex flex-col justify-center items-center py-10">
              <Loader2 className="h-10 w-10 animate-spin text-blue-500 mb-3" />
              <span className="text-gray-600 font-medium">Đang tải dữ liệu...</span>
            </div>
          )}
          {error && (
            <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-700 font-medium">{error}</p>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                className="flex-shrink-0 bg-white text-gray-700 border border-gray-300 hover:bg-gray-10"
                onClick={() => setError(null)}
              >
                Đóng
              </Button>
            </div>
          )}

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="flex">
              <div className="w-full md:w-96 border-r">
                <div className="p-4 flex items-center gap-3">
                  <div className="relative w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <Input 
                      placeholder="Tìm kiếm trang, session ID, tin nhắn..." 
                      className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                      value={search} 
                      onChange={(e) => setSearch(e.target.value)} 
                    />
                  </div>
                </div>
                <div className="px-4 pb-4 flex items-center gap-3">
                  <Select value={botFilter ?? undefined} onValueChange={(v) => setBotFilter(v === "__all__" ? undefined : v)}>
                    <SelectTrigger className="w-[160px]"><SelectValue placeholder="Tất cả Bot" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">Tất cả Bot</SelectItem>
                      {Array.from(new Set(histories.map((h) => String(h.bot_id || ""))).values()).filter((v) => v).map((v) => (
                        <SelectItem key={v} value={v}>{v}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={pageFilter ?? undefined} onValueChange={(v) => setPageFilter(v === "__all__" ? undefined : v)}>
                    <SelectTrigger className="w-[160px]"><SelectValue placeholder="Tất cả trang" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">Tất cả trang</SelectItem>
                      {Array.from(new Set(histories.map((h) => String(h.social_page_id || ""))).values()).filter((v) => v).map((v) => (
                        <SelectItem key={v} value={v}>{v}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="h-[560px] overflow-y-auto">
                  {sessions.map((s) => {
                    const msgs = histories.filter((h) => String(h.session_id || "") === String(s.id));
                    const latest = msgs[msgs.length - 1];
                    const active = String(activeSessionId || "") === String(s.id);
                    return (
                      <div key={String(s.id)} className={`px-4 py-3 border border-gray-200 rounded-xl mx-4 mb-3 cursor-pointer transition-all duration-200 ${active ? "bg-blue-50 border-blue-300 shadow-md" : "bg-white hover:bg-gray-50 hover:border-blue-300 hover:shadow-md"}`} onClick={() => { if (latest) openChat(latest); else setActiveSessionId(String(s.id)); }}>
                        <div className="flex items-center justify-between">
                          <div className="font-medium truncate">{latest?.text || String(s.id)}</div>
                          <div className="text-xs text-gray-500">{formatRelativeTime(latest?.created_at || s.last_activity || "")}</div>
                        </div>
                        <div className="mt-1 text-xs text-gray-600 truncate">{latest ? `Page: ${String(latest.social_page_id || "")} • Bot: ${String(latest.bot_id || "")}` : ""}</div>
                        <div className="mt-2 flex items-center justify-end gap-2">
                          <Button variant="outline" size="sm" className="bg-white flex items-center gap-2 hover:bg-red-50 hover:text-red-600 hover:border-red-300" onClick={(e) => { e.stopPropagation(); removeSession(s.id); }}>
                            <Trash2 className="w-4 h-4" />
                            Xóa
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                  {sessions.length === 0 && (
                    <div className="p-12 text-center">
                      <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                        <MessageSquare className="w-10 h-10 text-gray-400" />
                      </div>
                      <h3 className="text-xl font-semibold text-gray-900 mb-2">Chưa có phiên nào</h3>
                      <p className="text-gray-500">Khi có hội thoại, phiên sẽ xuất hiện tại đây</p>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex-1 min-h-[560px]">
                {!activeSessionId && (
                  <div className="h-full flex items-center justify-center text-gray-500">Chọn một phiên để xem chi tiết</div>
                )}
                {activeSessionId && (
                  <div className="h-full flex flex-col">
                    <div className="p-4 border-b flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {pageInfo?.fb_page_avatar && (
                          <Image src={pageInfo.fb_page_avatar} alt="avatar" width={36} height={36} className="rounded-full object-cover border" />
                        )}
                        <div>
                          <div className="font-semibold">{pageInfo?.fb_page_name || pageInfo?.name || pageInfo?.title || String(activeSessionId || "Chi tiết phiên")}</div>
                          <div className="text-xs text-gray-600">{activeRecord ? `Cập nhật: ${formatRelativeTime(activeRecord.created_at || "")}` : ""}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm">Tự động trả lời</span>
                          <button className={`relative inline-flex h-6 w-11 items-center rounded-full ${autoReply ? "bg-blue-600" : "bg-gray-300"}`} onClick={() => setAutoReply((v) => !v)}>
                            <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${autoReply ? "translate-x-5" : "translate-x-1"}`} />
                          </button>
                        </div>
                        <div className="text-xs text-gray-600">Tổng số tin nhắn: {sessionMessages.length}</div>
                        {activeSessionId && (
                          <Button variant="outline" size="sm" className="bg-white" onClick={() => removeSession(activeSessionId)}>Xóa phiên</Button>
                        )}
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                      {detailLoading && (
                        <div className="flex items-center gap-2 text-sm text-gray-500">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Đang tải phiên...
                        </div>
                      )}
                      {sessionMessages.map((m) => (
                        <div key={String(m.id)} className={`flex ${m.direction === "out" ? "justify-end" : "justify-start"}`}>
                          <div className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${m.direction === "out" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-800"}`}>
                            <div>{m.text || ""}</div>
                            <div className={`mt-1 text-[11px] ${m.direction === "out" ? "text-blue-100" : "text-gray-500"}`}>{formatRelativeTime(m.created_at || "")}</div>
                          </div>
                        </div>
                      ))}
                      {sessionMessages.length === 0 && (
                        <div className="h-full flex items-center justify-center text-gray-500">Không có tin nhắn trong phiên này</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "notifications" && (
        <div>
          <div className="mb-4 flex items-center gap-3">
            <Input placeholder="Tìm kiếm notifications ID, tiêu đề, hoặc bot..." value={notifSearch} onChange={(e) => setNotifSearch(e.target.value)} />
            <Button variant="outline" className="bg-white">Lọc</Button>
          </div>
          {loading && (
            <div className="flex flex-col justify-center items-center py-10">
              <Loader2 className="h-10 w-10 animate-spin text-blue-500 mb-3" />
              <span className="text-gray-600 font-medium">Đang tải dữ liệu...</span>
            </div>
          )}
          {error && (
            <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-red-700 font-medium">{error}</p>
              </div>
              <Button 
                variant="outline" 
                size="sm" 
                className="flex-shrink-0 bg-white text-gray-700 border border-gray-300 hover:bg-gray-10"
                onClick={() => setError(null)}
              >
                Đóng
              </Button>
            </div>
          )}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b text-xs text-gray-600">
              <div className="col-span-2">Notifications ID</div>
              <div className="col-span-5">Nội dung</div>
              <div className="col-span-2">Độ ưu tiên</div>
              <div className="col-span-1">Trạng thái</div>
              <div className="col-span-1">Thời gian</div>
              <div className="col-span-1">Thao tác</div>
            </div>
            {filteredNotifications.map((n) => (
              <div key={String(n.id)} className="grid grid-cols-12 gap-2 px-4 py-3 border-t items-center text-sm">
                <div className="col-span-2 truncate">{String(n.id)}</div>
                <div className="col-span-5 truncate">
                  <div className="font-medium">{n.title || "Không có tiêu đề"}</div>
                  <div className="text-gray-700 text-xs mt-1 truncate">{n.content || ""}</div>
                </div>
                <div className="col-span-2">
                  <span className="text-yellow-500">{"★".repeat(Math.max(1, Math.min(5, Number(n.priority) || 3)))}</span>
                  <span className="text-xs text-gray-500 ml-1">({n.priority || 3})</span>
                </div>
                <div className="col-span-1">
                  <span className={`px-2 py-1 rounded-full text-xs ${n.is_read ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{n.is_read ? "Đã đọc" : "Chưa đọc"}</span>
                </div>
                <div className="col-span-1 text-xs text-gray-600">{n.created_at || ""}</div>
                <div className="col-span-1 flex items-center gap-2">
                  <Button variant="outline" size="sm" className="bg-white" onClick={() => markRead(n.id, !n.is_read)}>{n.is_read ? "Chưa đọc" : "Đã đọc"}</Button>
                  <Button variant="outline" size="sm" className="bg-white text-red-600" onClick={() => removeNotification(n.id)}>Xóa</Button>
                </div>
              </div>
            ))}
            {filteredNotifications.length === 0 && (
              <div className="p-12 text-center">
                <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <Bell className="w-10 h-10 text-gray-400" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">Chưa có thông báo</h3>
                <p className="text-gray-500">Thông báo mới sẽ xuất hiện tại đây</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeRecord && pageInfo && (
        <div className="sr-only" aria-hidden>
          {JSON.stringify(pageInfo)}
        </div>
      )}
      </div>
    </div>
  );
}
