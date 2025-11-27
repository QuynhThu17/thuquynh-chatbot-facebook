"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getBots, type Bot, deleteBot, activateBot, deactivateBot } from "@/lib/api";
import { Loader2, AlertCircle, Eye, Rocket, Trash2, Grid3x3, List, Play, Square } from "lucide-react";
import { BotDetailsModal } from "@/components/bot-details-modal";
import { DeployBotModal } from "@/components/deploy-bot-modal";

export default function BotsPage() {
  const router = useRouter();
  const [bots, setBots] = useState<Bot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [viewMode, setViewMode] = useState<"list" | "grid">("grid");
  const [selectedBot, setSelectedBot] = useState<Bot | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [deployBot, setDeployBot] = useState<Bot | null>(null);
  const [isDeployOpen, setIsDeployOpen] = useState(false);

  useEffect(() => {
    fetchBots();
  }, []);

  const fetchBots = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getBots();
      if (response.success) {
        setBots(response.data);
      } else {
        setError(response.message || "Không thể tải danh sách bot");
      }
    } catch (err: any) {
      setError(err.message || "Lỗi kết nối đến máy chủ");
    } finally {
      setLoading(false);
    }
  };

  const filteredBots = bots.filter(bot => {
    const matchesSearch = bot.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || bot.status === statusFilter;
    const matchesType = typeFilter === "all" || bot.type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Quản lý Bot</h1>
          <p className="text-gray-500">Tạo, cấu hình và triển khai AI của bạn</p>
        </div>
        <Button className="bg-blue-600 hover:bg-blue-700">
          <span className="mr-2">+</span>
          Tạo Bot mới
        </Button>
      </div>

      {/* Stats Card */}
      <div className="bg-white rounded-lg border p-6 mb-6">
        <div className="flex items-center gap-3 text-gray-600">
          <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <div className="text-sm text-gray-500">Tổng số Bot</div>
            <div className="text-2xl font-bold text-gray-900">{bots.length}</div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <Input 
              placeholder="Tìm kiếm bot..." 
              className="pl-10 w-64" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
              </svg>
              <SelectValue placeholder="Tất cả trạng thái" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả trạng thái</SelectItem>
              <SelectItem value="active">Đang hoạt động</SelectItem>
              <SelectItem value="inactive">Không hoạt động</SelectItem>
            </SelectContent>
          </Select>

          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Tất cả loại" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả loại</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* View Toggle */}
        <div className="flex gap-2">
          <Button
            variant={viewMode === "grid" ? "default" : "outline"}
            size="icon"
            onClick={() => setViewMode("grid")}
            className={viewMode === "grid" ? "bg-blue-600 text-white" : "bg-white"}
          >
            <Grid3x3 className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === "list" ? "default" : "outline"}
            size="icon"
            onClick={() => setViewMode("list")}
            className={viewMode === "list" ? "bg-blue-600 text-white" : "bg-white"}
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex justify-center items-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <span className="ml-2 text-gray-500">Đang tải danh sách bot...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="flex justify-center items-center py-12">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
            <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
            <span className="text-red-700">{error}</span>
            <Button 
              variant="outline" 
              size="sm" 
              className="ml-4"
              onClick={fetchBots}
            >
              Thử lại
            </Button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && filteredBots.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">Không tìm thấy bot nào</p>
        </div>
      )}

      {/* Bots List/Grid */}
      {!loading && !error && filteredBots.length > 0 && (
        <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" : "space-y-4"}>
          {filteredBots.map((bot, index) => (
            <div 
              key={bot.id ? `${String(bot.id)}-${index}` : `${bot.name}-${index}`}
              className="bg-white rounded-lg border p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 flex-1">
                  {index + 1}. {bot.name}
                </h3>
                <button className="text-gray-400 hover:text-gray-600">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                  </svg>
                </button>
              </div>

              <div className="space-y-2 mb-4">
                <div className="text-sm">
                  <span className="text-gray-500">Vai trò:</span>
                  <span className="ml-2 text-gray-700 line-clamp-2">{bot.role}</span>
                </div>
                
                <div className="text-sm">
                  <span className="text-gray-500">Mục tiêu:</span>
                  <span className="ml-2 text-gray-700 line-clamp-2">{bot.target}</span>
                </div>

                <div className="text-sm">
                  <span className="text-gray-500">Nhiệm vụ:</span>
                  <span className="ml-2 text-gray-700 line-clamp-2">{bot.mission}</span>
                </div>

                {bot.note && (
                  <div className="text-sm">
                    <span className="text-gray-500">Ghi chú:</span>
                    <span className="ml-2 text-gray-700 line-clamp-1">{bot.note}</span>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-2 bg-white"
                  onClick={() => {
                    setSelectedBot(bot);
                    setIsDetailsOpen(true);
                  }}
                >
                  <Eye className="h-4 w-4" />
                  Xem
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-2 bg-white"
                  onClick={() => router.push(`/bots/knowledge?bot_id=${encodeURIComponent(String(bot.id))}`)}
                >
                  Kiến thức
                </Button>
                <Button size="sm" className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white" onClick={() => { setDeployBot(bot); setIsDeployOpen(true); }}>
                  <Rocket className="h-4 w-4" />
                  Triển khai
                </Button>
                <Button
                  size="sm"
                  className={`flex items-center gap-2 ${String(bot.status || "").toLowerCase() === "active" ? "bg-red-600 hover:bg-red-700 text-white" : "bg-green-600 hover:bg-green-700 text-white"}`}
                  onClick={async () => {
                    const active = String(bot.status || "").toLowerCase() === "active";
                    try {
                      const res = active ? await deactivateBot(bot.id) : await activateBot(bot.id);
                      if (res?.success !== false) {
                        setBots((prev) => prev.map((b) => (b.id === bot.id ? { ...b, status: active ? "inactive" : "active" } : b)));
                      }
                    } catch (err: any) {
                      setError(err?.message || (active ? "Không thể tắt bot" : "Không thể bật bot"));
                    }
                  }}
                >
                  {String(bot.status || "").toLowerCase() === "active" ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  {String(bot.status || "").toLowerCase() === "active" ? "Tắt" : "Bật"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-2 text-red-600 hover:text-red-700 hover:bg-red-50 bg-white"
                  onClick={async () => {
                    const ok = typeof window !== "undefined" ? window.confirm("Xóa bot này?") : true;
                    if (!ok) return;
                    const res = await deleteBot(bot.id);
                    if (res?.success !== false) {
                      setBots((prev) => prev.filter((b) => b.id !== bot.id));
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Details Modal */}
      {isDetailsOpen && selectedBot && (
        <BotDetailsModal bot={selectedBot} open={true} onClose={() => setIsDetailsOpen(false)} />
      )}
      <DeployBotModal bot={deployBot} open={isDeployOpen} onClose={() => setIsDeployOpen(false)} />
    </div>
  );
}