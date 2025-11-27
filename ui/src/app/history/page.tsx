"use client";
import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getHistories, getHistorySessions, deleteHistorySession, getNotifications, markNotificationRead, markNotificationUnread, deleteNotification, getSocialPageById } from "@/lib/api";

type Tab = "histories" | "notifications";

export default function HistoryPage() {
  const [tab, setTab] = useState<Tab>("histories");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [pageFilter, setPageFilter] = useState<string | undefined>(undefined);
  const [botFilter, setBotFilter] = useState<string | undefined>(undefined);

  const [histories, setHistories] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);

  const [activeRecord, setActiveRecord] = useState<any | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | number | null>(null);
  const [pageInfo, setPageInfo] = useState<any | null>(null);
  const [autoReply, setAutoReply] = useState<boolean>(true);
  const [sessionFeed, setSessionFeed] = useState<any[]>([]);
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

  useEffect(() => {
    setError(null);
    setLoading(true);
    const run = async () => {
      try {
        if (tab === "histories") {
          const res = await getHistories({ social_page_id: pageFilter, bot_id: botFilter, limit: 50 });
          setHistories(res?.data || []);
          const sRes = await getHistorySessions({ limit: 20 });
          setSessions(sRes?.data || []);
        } else {
          const nRes = await getNotifications({ limit: 50 });
          setNotifications(nRes?.data || []);
        }
      } catch (e: any) {
        setError(e?.message || "Lỗi tải dữ liệu");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [tab, pageFilter, botFilter]);

  const openChat = async (record: any) => {
    setActiveRecord(record);
    setActiveSessionId(record?.session_id ?? null);
    setDetailLoading(true);
    setPageInfo(null);
    try {
      const [piRes, mr] = await Promise.all([
        record?.social_page_id ? getSocialPageById("s_facebook", record.social_page_id) : Promise.resolve(null),
        getHistories({ session_id: String(record?.session_id || ""), limit: 100 })
      ]);
      if (piRes) setPageInfo((piRes as any)?.data || null);
      const raw = (mr?.data || []) as any[];
      const expanded: any[] = [];
      for (const it of raw) {
        const created = it?.created_at ? new Date(it.created_at).getTime() : 0;
        const updated = it?.updated_at ? new Date(it.updated_at).getTime() : created;
        if (it?.query) expanded.push({ id: `${it.id}_q`, direction: "in", text: it.query, created_at: it?.created_at || it?.time || it?.timestamp });
        if (it?.answer) expanded.push({ id: `${it.id}_a`, direction: "out", text: it.answer, created_at: it?.updated_at || it?.created_at || it?.time || it?.timestamp });
        if (!it?.query && !it?.answer) expanded.push({ id: it.id, direction: it.direction, text: it.text, created_at: it?.created_at });
      }
      const msgs = expanded.slice().sort((a: any, b: any) => {
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
        const raw = (mr?.data || []) as any[];
        const expanded: any[] = [];
        for (const it of raw) {
          if (it?.query) expanded.push({ id: `${it.id}_q`, direction: "in", text: it.query, created_at: it?.created_at || it?.time || it?.timestamp });
          if (it?.answer) expanded.push({ id: `${it.id}_a`, direction: "out", text: it.answer, created_at: it?.updated_at || it?.created_at || it?.time || it?.timestamp });
          if (!it?.query && !it?.answer) expanded.push({ id: it.id, direction: it.direction, text: it.text, created_at: it?.created_at });
        }
        const msgs = expanded.slice().sort((a: any, b: any) => {
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
  }, [activeSessionId]);

  const markRead = async (id: string | number, read: boolean) => {
    try {
      if (read) await markNotificationRead(id);
      else await markNotificationUnread(id);
      setNotifications((prev) => prev.map((n) => (String(n.id) === String(id) ? { ...n, is_read: read } : n)));
    } catch {}
  };

  const removeSession = async (id: string | number) => {
    try {
      await deleteHistorySession(id);
      setSessions((prev) => prev.filter((s) => String(s.id) !== String(id)));
    } catch {}
  };

  const removeNotification = async (id: string | number) => {
    try {
      await deleteNotification(id);
      setNotifications((prev) => prev.filter((n) => String(n.id) !== String(id)));
    } catch {}
  };

  const filteredHistories = histories.filter((h) => {
    const t = (h?.text || "").toLowerCase();
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return t.includes(q);
  });

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
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Lịch sử & Hộp thư</h1>
        <p className="text-gray-500">Quản lý cuộc trò chuyện, phản hồi và thông báo</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white text-gray-900 border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cuộc trò chuyện</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{conversationCount}</div>
          </CardContent>
        </Card>
        <Card className="bg-white text-gray-900 border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Phản hồi</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{replyCount}</div>
          </CardContent>
        </Card>
        <Card className="bg-white text-gray-900 border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Thông báo</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="text-2xl font-bold">{notifications.length}</div>
              <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-600">{unreadNotificationsCount} chưa đọc</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex items-center gap-2 mb-6">
        <Button variant="outline" className="bg-white" onClick={() => setTab("histories")}>Cuộc trò chuyện</Button>
        <Button variant="outline" className="bg-white" onClick={() => setTab("notifications")}>Thông báo</Button>
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
            <div className="text-sm text-gray-600">Đang tải dữ liệu...</div>
          )}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm mb-4">{error}</div>
          )}

          <div className="rounded-lg border bg-white">
            <div className="flex">
              <div className="w-full md:w-96 border-r">
                <div className="p-4 flex items-center gap-3">
                  <div className="relative w-full">
                    <Input placeholder="Tìm kiếm trang, session ID, tin nhắn..." value={search} onChange={(e) => setSearch(e.target.value)} />
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
                      <div key={String(s.id)} className={`px-4 py-3 border-t cursor-pointer ${active ? "bg-blue-50" : "bg-white hover:bg-gray-50"}`} onClick={() => { if (latest) openChat(latest); else setActiveSessionId(String(s.id)); }}>
                        <div className="flex items-center justify-between">
                          <div className="font-medium truncate">{latest?.text || String(s.id)}</div>
                          <div className="text-xs text-gray-500">{formatRelativeTime(latest?.created_at || s.last_activity || "")}</div>
                        </div>
                        <div className="mt-1 text-xs text-gray-600 truncate">{latest ? `Page: ${String(latest.social_page_id || "")} • Bot: ${String(latest.bot_id || "")}` : ""}</div>
                        <div className="mt-2 flex items-center justify-end gap-2">
                          <Button variant="outline" size="sm" className="bg-white" onClick={(e) => { e.stopPropagation(); removeSession(s.id); }}>Xóa</Button>
                        </div>
                      </div>
                    );
                  })}
                  {sessions.length === 0 && (
                    <div className="p-4 text-sm text-gray-600">Không có phiên</div>
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
                          <img src={pageInfo.fb_page_avatar} alt="avatar" className="w-9 h-9 rounded-full object-cover border" />
                        )}
                        <div>
                          <div className="font-semibold">{pageInfo?.fb_page_name || pageInfo?.name || pageInfo?.title || String(activeRecord?.social_page_id || activeSessionId || "Chi tiết phiên")}</div>
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
                        {activeRecord && (
                          <Button variant="outline" size="sm" className="bg-white" onClick={() => removeSession(activeRecord.session_id)}>Xóa phiên</Button>
                        )}
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                      {detailLoading && (
                        <div className="text-sm text-gray-500">Đang tải phiên...</div>
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
            <div className="text-sm text-gray-600">Đang tải dữ liệu...</div>
          )}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm mb-4">{error}</div>
          )}
          <div className="rounded-lg border bg-white">
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
              <div className="px-4 py-8 text-center text-sm text-gray-600">Không có thông báo</div>
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
  );
}