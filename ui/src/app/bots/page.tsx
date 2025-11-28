"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { type Bot } from "@/lib/api";
import { useBotsQuery, useDeleteBotMutation, useActivateBotMutation, useDeactivateBotMutation } from "@/lib/queries";
import { Loader2, AlertCircle, Eye, Rocket, Trash2, Grid3x3, List, Play, Square, Plus, MoreVertical, BookOpen } from "lucide-react";
import { BotDetailsModal } from "@/components/bot-details-modal";
import { DeployBotModal } from "@/components/deploy-bot-modal";

export default function BotsPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [viewMode, setViewMode] = useState<"list" | "grid">("grid");
  const [selectedBot, setSelectedBot] = useState<Bot | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [deployBot, setDeployBot] = useState<Bot | null>(null);
  const [isDeployOpen, setIsDeployOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const botsQuery = useBotsQuery();
  const bots = (botsQuery.data as Bot[]) || [];
  const loading = botsQuery.isLoading;

  const actMut = useActivateBotMutation();
  const deactMut = useDeactivateBotMutation();
  const delMut = useDeleteBotMutation();

  const handleToggleStatus = async (bot: Bot) => {
    const statusStr = String(bot.status || "").toLowerCase();
    const isActive = statusStr === "active" || statusStr === "on";
    const actionKey = `toggle-${bot.id}`;
    
    try {
      setActionLoading(actionKey);
      if (isActive) await deactMut.mutateAsync(bot.id); else await actMut.mutateAsync(bot.id);
    } catch (err: any) {
      setError(err?.message || (isActive ? "Không thể tắt bot" : "Không thể bật bot"));
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteBot = async (bot: Bot) => {
    if (!confirm(`Bạn có chắc chắn muốn xóa bot "${bot.name}"?`)) return;
    
    const actionKey = `delete-${bot.id}`;
    try {
      setActionLoading(actionKey);
      await delMut.mutateAsync(bot.id);
    } catch (err: any) {
      setError(err?.message || "Không thể xóa bot");
    } finally {
      setActionLoading(null);
    }
  };

  const filteredBots = bots.filter(bot => {
    const matchesSearch = bot.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || bot.status === statusFilter;
    const matchesType = typeFilter === "all" || bot.type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  const activeBots = bots.filter(b => String(b.status || "").toLowerCase() === "active").length;
  const inactiveBots = bots.length - activeBots;

  return (
    <div className="min-h-screen from-slate-50 to-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black mb-2">
              Quản lý Bot
            </h1>
            <p className="text-gray-600">Tạo, cấu hình và triển khai AI của bạn một cách dễ dàng</p>
          </div>
          <Button 
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
            onClick={() => router.push('/bots/create')}
          >
            <Plus className="mr-2 h-5 w-5" />
            Tạo Bot mới
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Tổng số Bot</div>
                <div className="text-3xl font-bold text-gray-900">{bots.length}</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-md">
                <Play className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Đang hoạt động</div>
                <div className="text-3xl font-bold text-gray-900">{activeBots}</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-gray-400 to-gray-500 flex items-center justify-center shadow-md">
                <Square className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Không hoạt động</div>
                <div className="text-3xl font-bold text-gray-900">{inactiveBots}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1">
              <div className="relative flex-1 max-w-md">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <Input 
                  placeholder="Tìm kiếm theo tên bot..." 
                  className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500" 
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[180px] border-gray-300">
                  <SelectValue placeholder="Trạng thái" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả trạng thái</SelectItem>
                  <SelectItem value="active">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-green-500"></span>
                      Đang hoạt động
                    </span>
                  </SelectItem>
                  <SelectItem value="inactive">
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-gray-400"></span>
                      Không hoạt động
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>

              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-full sm:w-[180px] border-gray-300">
                  <SelectValue placeholder="Loại bot" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả loại</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* View Toggle */}
            <div className="flex gap-2">
              <Button
                size="icon"
                onClick={() => setViewMode("grid")}
                className={
                  viewMode === "grid"
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"
                }
              >
                <Grid3x3 className="h-4 w-4" />
              </Button>

              <Button
                size="icon"
                onClick={() => setViewMode("list")}
                className={
                  viewMode === "list"
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"
                }
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 animate-in fade-in duration-300">
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

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col justify-center items-center py-20">
            <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
            <span className="text-gray-600 font-medium">Đang tải danh sách bot...</span>
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredBots.length === 0 && !error && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
              <svg className="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {searchTerm || statusFilter !== "all" || typeFilter !== "all" 
                ? "Không tìm thấy bot phù hợp" 
                : "Chưa có bot nào"}
            </h3>
            <p className="text-gray-500 mb-6">
              {searchTerm || statusFilter !== "all" || typeFilter !== "all"
                ? "Thử điều chỉnh bộ lọc để tìm kiếm bot khác"
                : "Bắt đầu tạo bot đầu tiên của bạn ngay bây giờ"}
            </p>
            {!(searchTerm || statusFilter !== "all" || typeFilter !== "all") && (
              <Button 
                className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                onClick={() => router.push('/bots/create')}
              >
                <Plus className="mr-2 h-5 w-5" />
                Tạo Bot mới
              </Button>
            )}
          </div>
        )}

        {/* Bots Grid/List */}
        {!loading && filteredBots.length > 0 && (
          <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
            {filteredBots.map((bot, index) => {
              const statusStr = String(bot.status || "").toLowerCase();
              const isActive = statusStr === "active" || statusStr === "on";
              const toggleLoading = actionLoading === `toggle-${bot.id}`;
              const deleteLoading = actionLoading === `delete-${bot.id}`;
              
              return (
                <div 
                  key={bot.id ? `${String(bot.id)}-${index}` : `${bot.name}-${index}`}
                  className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-all duration-200 hover:border-blue-300"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3 flex-1">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold shadow-md ${
                        isActive ? 'bg-gradient-to-br from-green-500 to-green-600' : 'bg-gradient-to-br from-gray-400 to-gray-500'
                      }`}>
                        {bot.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-gray-900 whitespace-normal">
                          {bot.name}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`w-2 h-2 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-400'}`}></span>
                          <span className={`text-xs font-medium ${isActive ? 'text-green-600' : 'text-gray-500'}`}>
                            {isActive ? 'Hoạt động' : 'Không hoạt động'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="space-y-3 mb-6">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xs text-gray-500 font-medium mb-1">Vai trò</div>
                      <div className="text-sm text-gray-700 line-clamp-2">{bot.role || "Chưa cập nhật"}</div>
                    </div>
                    
                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xs text-gray-500 font-medium mb-1">Mục tiêu</div>
                      <div className="text-sm text-gray-700 line-clamp-2">{bot.target || "Chưa cập nhật"}</div>
                    </div>

                    <div className="bg-gray-50 rounded-lg p-3">
                      <div className="text-xs text-gray-500 font-medium mb-1">Nhiệm vụ</div>
                      <div className="text-sm text-gray-700 line-clamp-2">{bot.mission || "Chưa cập nhật"}</div>
                    </div>

                    {bot.note && (
                      <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                        <div className="text-xs text-blue-600 font-medium mb-1">Ghi chú</div>
                        <div className="text-sm text-gray-700 line-clamp-1">{bot.note}</div>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-2 bg-white hover:bg-white-50 hover:text-blue-600 hover:border-blue-300"
                      onClick={() => {
                        setSelectedBot(bot);
                        setIsDetailsOpen(true);
                      }}
                    >
                      <Eye className="bg-white h-4 w-4" />
                      <span className="hidden bg-white sm:inline">Chi tiết</span>
                    </Button>
                    
                    {/* <Button
                      variant="outline"
                      size="sm"
                      className="bg-white flex items-center gap-2 hover:bg-purple-50 hover:text-purple-600 hover:border-purple-300"
                      onClick={() => router.push(`/bots/knowledge?bot_id=${encodeURIComponent(String(bot.id))}`)}
                    >
                      <BookOpen className="h-4 w-4" />
                      <span className="hidden sm:inline">Kiến thức</span>
                    </Button> */}
                    
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={toggleLoading}
                      className={`bg-white flex items-center gap-2 ${
                        isActive 
                          ? "hover:bg-red-50 hover:text-red-600 hover:border-red-300" 
                          : "hover:bg-green-50 hover:text-green-600 hover:border-green-300"
                      }`}
                      onClick={() => handleToggleStatus(bot)}
                    >
                      {toggleLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : isActive ? (
                        <Square className="h-4 w-4" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                      <span className="hidden sm:inline">{isActive ? "Tắt" : "Bật"}</span>
                    </Button>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={deleteLoading}
                      className="bg-white flex items-center gap-2 hover:bg-red-50 hover:text-red-600 hover:border-red-300"
                      onClick={() => handleDeleteBot(bot)}
                    >
                      {deleteLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>

                    <Button 
                      size="sm" 
                      className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                      onClick={() => { 
                        setDeployBot(bot); 
                        setIsDeployOpen(true); 
                      }}
                    >
                      <Rocket className="h-4 w-4" />
                      <span className="hidden sm:inline">Triển khai</span>
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Modals */}
        {isDetailsOpen && selectedBot && (
          <BotDetailsModal 
            bot={selectedBot} 
            open={true} 
            onClose={() => {
              setIsDetailsOpen(false);
              setSelectedBot(null);
            }} 
          />
        )}
        
        <DeployBotModal 
          bot={deployBot} 
          open={isDeployOpen} 
          onClose={() => {
            setIsDeployOpen(false);
            setDeployBot(null);
          }} 
        />
      </div>
    </div>
  );
}
