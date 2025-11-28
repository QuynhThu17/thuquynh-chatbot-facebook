"use client";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { type SocialPage, getBots, type Bot, connectBotToSocial, disconnectBotFromSocial } from "@/lib/api";
import { useSocialPagesQuery } from "@/lib/queries";
import { RefreshCcw, Loader2, Grid3x3, List, PlugZap } from "lucide-react";

export function SocialPagesModal({ open, onClose, socialId, accountId }: { open: boolean; onClose: () => void; socialId: string; accountId: string }) {
  const [pages, setPages] = useState<SocialPage[]>([]);
  const pagesQuery = useSocialPagesQuery(socialId, accountId);
  const loading = pagesQuery.isLoading && pages.length === 0;
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "grid">("grid");
  const [selectOpen, setSelectOpen] = useState(false);
  const [selectedPage, setSelectedPage] = useState<SocialPage | null>(null);
  const [bots, setBots] = useState<Bot[]>([]);
  const [botSearch, setBotSearch] = useState("");
  const [selectedBotId, setSelectedBotId] = useState<string | number | null>(null);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setSearchTerm("");
    const rows = pagesQuery.data as SocialPage[] | undefined;
    if (Array.isArray(rows)) setPages(rows);
  }, [open, pagesQuery.data]);

  const reload = async () => { await pagesQuery.refetch(); };

  const filtered = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return pages;
    return pages.filter((p) => (p.name || String(p.id)).toLowerCase().includes(q));
  }, [pages, searchTerm]);

  const connectedCount = useMemo(() => {
    return pages.filter((p) => !!p.is_connected).length;
  }, [pages]);

  const openSelectBot = async (page: SocialPage) => {
    setSelectedPage(page);
    setSelectOpen(true);
    try {
      const res = await getBots();
      setBots(res.data || []);
      setSelectedBotId(null);
      setBotSearch("");
    } catch {}
  };

  const filteredBots = useMemo(() => {
    const q = botSearch.trim().toLowerCase();
    const rows = bots;
    if (!q) return rows;
    return rows.filter((b) => b.name.toLowerCase().includes(q));
  }, [bots, botSearch]);

  const connect = async () => {
    if (!selectedPage || selectedBotId === null) return;
    try {
      setConnecting(true);
      await connectBotToSocial(selectedBotId, { social_id: socialId, social_page_id: selectedPage.id });
      await reload();
      setSelectOpen(false);
      setSelectedPage(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Kết nối thất bại";
      setError(msg);
    } finally {
      setConnecting(false);
    }
  };

  const findConnectedBotIdForPage = async (pageId: string | number): Promise<string | number | null> => {
    try {
      const list = bots.length === 0 ? ((await getBots()).data || []) : bots;
      if (bots.length === 0) setBots(list);
      type Connection = { social_page_id?: string | number; social_id?: string | number };
      for (const b of list) {
        const c: unknown = b.connect;
        let arr: Connection[] = [];
        if (Array.isArray(c)) arr = c as Connection[];
        else if (typeof c === "string") {
          try {
            const parsed = JSON.parse(c);
            if (Array.isArray(parsed)) arr = parsed as Connection[];
          } catch {}
        }
        if (arr.some((conn) => String(conn?.social_page_id) === String(pageId))) {
          return b.id;
        }
      }
    } catch {}
    return null;
  };

  const onTogglePage = async (page: SocialPage) => {
    const connected = !!page.is_connected;
    if (!connected) {
      await openSelectBot(page);
      return;
    }
    try {
      setConnecting(true);
      const botId = await findConnectedBotIdForPage(page.id);
      if (botId === null) {
        setError("Không tìm thấy bot đang kết nối cho trang này");
        return;
      }
      await disconnectBotFromSocial(botId, page.id);
      await reload();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Ngắt kết nối thất bại";
      setError(msg);
    } finally {
      setConnecting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-4xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 p-6 border-b">
            <div>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black">Quản lý Trang Facebook</h2>
              <p className="text-gray-600">Kết nối trang với Bot để tự động hóa</p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="bg-white" onClick={reload}><RefreshCcw className="w-4 h-4 mr-2" />Tải lại</Button>
              <div className="flex gap-2">
                <Button
                  size="icon"
                  onClick={() => setViewMode("grid")}
                  className={viewMode === "grid" ? "bg-blue-600 text-white hover:bg-blue-700" : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"}
                >
                  <Grid3x3 className="h-4 w-4" />
                </Button>
                <Button
                  size="icon"
                  onClick={() => setViewMode("list")}
                  className={viewMode === "list" ? "bg-blue-600 text-white hover:bg-blue-700" : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"}
                >
                  <List className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>

          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                    <PlugZap className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 font-medium">Tổng số Trang</div>
                    <div className="text-3xl font-bold text-gray-900">{pages.length}</div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-md">
                    <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 font-medium">Đã kết nối</div>
                    <div className="text-3xl font-bold text-gray-900">{connectedCount}</div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-gray-400 to-gray-500 flex items-center justify-center shadow-md">
                    <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500 font-medium">Chưa kết nối</div>
                    <div className="text-3xl font-bold text-gray-900">{pages.length - connectedCount}</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
                <div className="relative flex-1 max-w-md">
                  <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <Input 
                    placeholder="Tìm kiếm trang..." 
                    className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500" 
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="bg-white" onClick={reload}><RefreshCcw className="w-4 h-4 mr-2" />Tải lại</Button>
                </div>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 animate-in fade-in duration-300">
                <svg className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12" y2="16"/></svg>
                <div className="flex-1">
                  <p className="text-red-700 font-medium">{error}</p>
                </div>
                <Button variant="outline" size="sm" className="flex-shrink-0 bg-white text-gray-700 border border-gray-300 hover:bg-gray-10" onClick={() => setError(null)}>Đóng</Button>
              </div>
            )}

            {loading && (
              <div className="flex flex-col justify-center items-center py-20">
                <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
                <span className="text-gray-600 font-medium">Đang tải danh sách trang...</span>
              </div>
            )}

            {!loading && filtered.length === 0 && !error && (
              <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
                <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                  <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">Không có trang nào</h3>
                <p className="text-gray-500">Hãy liên kết tài khoản Facebook để tải danh sách trang</p>
              </div>
            )}

            {!loading && filtered.length > 0 && (
              <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 gap-6" : "space-y-4"}>
                {filtered.map((p, index) => {
                  const connected = !!p.is_connected;
                  return (
                    <div key={p.id ? `${String(p.id)}-${index}` : `${p.name}-${index}`} className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-all duration-200 hover:border-blue-300">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3 flex-1">
                          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold shadow-md ${connected ? 'bg-gradient-to-br from-green-500 to-green-600' : 'bg-gradient-to-br from-gray-400 to-gray-500'}`}>{(p.name || String(p.id)).charAt(0).toUpperCase()}</div>
                          <div className="flex-1 min-w-0">
                            <div className="text-lg font-semibold text-gray-900 whitespace-normal">{p.name}</div>
                            <div className="flex items-center gap-2 mt-1">
                              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                              <span className={`text-xs font-medium ${connected ? 'text-green-600' : 'text-gray-500'}`}>{connected ? 'Đã kết nối' : 'Chưa kết nối'}</span>
                            </div>
                            <div className="text-xs text-gray-500 mt-1">{String(p.id)}</div>
                          </div>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className={`bg-white flex items-center gap-2 ${connected ? 'hover:bg-red-50 hover:text-red-600 hover:border-red-300' : 'hover:bg-green-50 hover:text-green-600 hover:border-green-300'}`}
                          onClick={() => onTogglePage(p)}
                          disabled={connecting}
                        >
                          {connecting ? (<Loader2 className="h-4 w-4 animate-spin" />) : (<PlugZap className="h-4 w-4" />)}
                          <span className="hidden sm:inline">{connected ? 'Ngắt kết nối' : 'Kết nối'}</span>
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">{connectedCount} / {pages.length} trang đã kết nối</div>
              <Button variant="outline" className="bg-white" onClick={onClose}>Xong</Button>
            </div>
          </div>
        </div>
      </div>

      {selectOpen && selectedPage && (
        <div className="fixed inset-0 z-[60]">
          <div className="absolute inset-0 bg-black/10" />
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="w-full max-w-xl bg-white rounded-xl border shadow-xl">
              <div className="flex items-center justify-between p-6 border-b">
                <div className="font-semibold">Chọn Bot cho Trang</div>
              </div>
              <div className="p-6 space-y-4">
                <div className="text-sm text-gray-600">{selectedPage.name}</div>
                <Input placeholder="Tìm kiếm bot..." value={botSearch} onChange={(e) => setBotSearch(e.target.value)} />
                <div className="space-y-2 max-h-64 overflow-auto">
                  {filteredBots.map((b) => (
                    <button key={String(b.id)} className="w-full text-left border rounded-lg p-3 flex items-center justify-between" onClick={() => setSelectedBotId(b.id)}>
                      <span>{b.name}</span>
                      {selectedBotId === b.id && <span className="text-xs text-blue-600">Đã chọn</span>}
                    </button>
                  ))}
                  {filteredBots.length === 0 && <div className="text-sm text-gray-600">Không có bot</div>}
                </div>
                <div className="flex items-center justify-end gap-2">
                  <Button variant="outline" className="bg-white" onClick={() => { setSelectOpen(false); setSelectedPage(null); }}>Hủy</Button>
                  <Button onClick={connect} disabled={selectedBotId === null || connecting} className="bg-blue-600 text-white">Kết nối</Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
