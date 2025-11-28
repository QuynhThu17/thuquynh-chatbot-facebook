"use client";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { type SocialPage, getBots, type Bot, connectBotToSocial, disconnectBotFromSocial } from "@/lib/api";
import { useSocialPagesQuery } from "@/lib/queries";
import { RefreshCcw } from "lucide-react";

export function SocialPagesModal({ open, onClose, socialId, accountId }: { open: boolean; onClose: () => void; socialId: string; accountId: string }) {
  const [pages, setPages] = useState<SocialPage[]>([]);
  const pagesQuery = useSocialPagesQuery(socialId, accountId);
  const loading = pagesQuery.isLoading && pages.length === 0;
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
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
        <div className="relative w-full max-w-3xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-6 border-b">
            <div className="flex items-center gap-2"><span className="font-semibold">Trang Facebook</span></div>
            <Button variant="outline" size="sm" className="bg-white" onClick={reload}><RefreshCcw className="w-4 h-4 mr-2" />Tải lại</Button>
          </div>
          <div className="p-6 space-y-4">
            <Input placeholder="Tìm kiếm trang..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
            {error && <div className="text-sm text-red-600">{error}</div>}
            {loading ? (
              <div className="text-gray-600">Đang tải...</div>
            ) : (
              <div className="space-y-3">
                {filtered.map((p) => {
                  const connected = !!p.is_connected;
                  return (
                    <div key={String(p.id)} className={`flex items-center justify-between border rounded-lg p-4 ${connected ? "bg-green-50" : ""}`}>
                      <div>
                        <div className="font-medium">{p.name}</div>
                        <div className="text-xs text-gray-500">{String(p.id)}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-1 rounded-full ${connected ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}`}>{connected ? "Đã kết nối" : "Chưa kết nối"}</span>
                        <button
                          className={`w-10 h-6 rounded-full ${connected ? "bg-blue-600" : "bg-gray-300"}`}
                          onClick={() => onTogglePage(p)}
                          disabled={connecting}
                        >
                          <span className={`block w-5 h-5 bg-white rounded-full transform transition ${connected ? "translate-x-5" : "translate-x-0"}`} />
                        </button>
                      </div>
                    </div>
                  );
                })}
                {filtered.length === 0 && <div className="text-sm text-gray-600">Không có trang nào</div>}
                <div className="text-sm text-gray-600">{connectedCount} trên {pages.length} trang đã kết nối</div>
              </div>
            )}
            <div className="flex items-center justify-end">
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
