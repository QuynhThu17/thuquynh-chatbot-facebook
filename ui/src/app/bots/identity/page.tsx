"use client";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AppWindow,
  Copy,
  Edit,
  Grip,
  List,
  MessageSquare,
  Eye,
  Plus,
  Search,
  Trash2,
  Loader2,
  AlertCircle,
  X,
} from "lucide-react";
import { type Identity, getIdentities, copyIdentity, deleteIdentity } from "@/lib/api";
import { IdentityDetailsModal } from "@/components/identity-details-modal";
import { CreateIdentityModal } from "@/components/create-identity-modal";

function IdentityCard({ 
  identity, 
  onCopy, 
  onView, 
  onEdit, 
  onDelete,
  isDeleting,
  isCopying 
}: { 
  identity: Identity; 
  onCopy: (id: Identity["id"]) => Promise<void>; 
  onView: (i: Identity) => void; 
  onEdit: (i: Identity) => void; 
  onDelete: (id: Identity["id"]) => Promise<void>;
  isDeleting: boolean;
  isCopying: boolean;
}) {
  return (
    <Card className="flex flex-col bg-white border border-gray-200 hover:shadow-lg transition-all duration-200 hover:border-blue-300">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base font-bold text-gray-900 flex-1">
            {identity.title}
          </CardTitle>
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-md">
            <AppWindow className="w-5 h-5 text-white" />
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="flex-grow space-y-4">
        <p className="text-sm text-gray-700 line-clamp-3 leading-relaxed">
          {identity.description || "Chưa có mô tả"}
        </p>
        
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-100">
            <MessageSquare className="w-3.5 h-3.5 text-blue-600" />
            <span className="text-xs font-medium text-blue-700">
              {identity.examples || 0} ví dụ
            </span>
          </div>
        </div>
      </CardContent>
      
      <div className="flex items-center justify-end gap-1 p-3 border-t border-gray-100">
        <Button
          variant="outline"
          size="sm"
          className="bg-white hover:bg-blue-50 hover:text-blue-600 hover:border-blue-300"
          onClick={() => onView(identity)}
        >
          <Eye className="h-4 w-4 mr-1.5" />
          <span className="hidden sm:inline">Xem</span>
        </Button>
        
        <Button 
          variant="ghost" 
          size="icon"
          className="hover:bg-purple-50 hover:text-purple-600"
          onClick={() => onEdit(identity)}
          disabled={isDeleting || isCopying}
          aria-label="Sửa danh tính"
        >
          <Edit className="w-4 h-4" />
        </Button>
        
        <Button 
          variant="ghost" 
          size="icon"
          className="hover:bg-green-50 hover:text-green-600"
          onClick={() => onCopy(identity.id)}
          disabled={isDeleting || isCopying}
          aria-label="Sao chép danh tính"
        >
          {isCopying ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </Button>
        
        <Button 
          variant="ghost" 
          size="icon" 
          className="hover:bg-red-50 hover:text-red-600"
          onClick={() => onDelete(identity.id)}
          disabled={isDeleting || isCopying}
          aria-label="Xóa danh tính"
        >
          {isDeleting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </Button>
      </div>
    </Card>
  );
}

export default function IdentityPage() {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selected, setSelected] = useState<Identity | null>(null);
  const [open, setOpen] = useState<boolean>(false);
  const [createOpen, setCreateOpen] = useState<boolean>(false);
  const [editOpen, setEditOpen] = useState<boolean>(false);
  const [editingIdentity, setEditingIdentity] = useState<Identity | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getIdentities();
        if (res.success) {
          setIdentities(res.data || []);
        } else {
          setError(res.message || "Không thể tải danh sách danh tính");
        }
      } catch (err: any) {
        setError(err.message || "Lỗi kết nối máy chủ");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return identities;
    return identities.filter((i) =>
      `${i.title} ${i.description || ""}`.toLowerCase().includes(term)
    );
  }, [identities, searchTerm]);

  const totalExamples = useMemo(
    () => identities.reduce((sum, i) => sum + (i.examples || 0), 0),
    [identities]
  );

  const onCopy = async (id: Identity["id"]) => {
    const actionKey = `copy-${id}`;
    setActionLoading(actionKey);
    try {
      const res = await copyIdentity(id);
      if (res?.success && res?.data) {
        setIdentities((prev) => [res.data, ...prev]);
      } else {
        setError(res?.message || "Không thể sao chép danh tính");
      }
    } catch (err: any) {
      setError(err?.message || "Không thể sao chép danh tính");
    } finally {
      setActionLoading(null);
    }
  };

  const onDelete = async (id: Identity["id"]) => {
    const identity = identities.find(i => i.id === id);
    if (!confirm(`Bạn có chắc chắn muốn xóa danh tính "${identity?.title}"?`)) return;
    
    const actionKey = `delete-${id}`;
    setActionLoading(actionKey);
    try {
      const res = await deleteIdentity(id);
      if (res?.success !== false) {
        setIdentities((prev) => prev.filter((p) => p.id !== id));
      } else {
        setError(res?.message || "Không thể xóa danh tính");
      }
    } catch (err: any) {
      setError(err?.message || "Không thể xóa danh tính");
    } finally {
      setActionLoading(null);
    }
  };

  const onView = (i: Identity) => {
    setSelected(i);
    setOpen(true);
  };

  return (
    <div className="min-h-screen bg-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl text-black font-bold bg-gradient-to-r from-purple-600 to-indigo-600 bg-clip-text mb-2">
              Quản lý Danh tính
            </h1>
            <p className="text-gray-600">Tạo và quản lý danh tính AI cho các tình huống khác nhau</p>
          </div>
          <Button 
            className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="mr-2 h-5 w-5" />
            Tạo Danh tính
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                Tổng số Danh tính
              </CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-md">
                <AppWindow className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{identities.length}</div>
              <p className="text-xs text-gray-500 mt-1">Danh tính đã tạo</p>
            </CardContent>
          </Card>

          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                Tổng số Ví dụ
              </CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <MessageSquare className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{totalExamples}</div>
              <p className="text-xs text-gray-500 mt-1">Ví dụ hội thoại</p>
            </CardContent>
          </Card>

          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                Trung bình
              </CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-md">
                <MessageSquare className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">
                {identities.length > 0 ? Math.round(totalExamples / identities.length) : 0}
              </div>
              <p className="text-xs text-gray-500 mt-1">Ví dụ / danh tính</p>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <Input
                placeholder="Tìm kiếm danh tính..."
                className="pl-10 border-gray-300 focus:border-purple-500 focus:ring-purple-500"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                size="icon"
                onClick={() => setViewMode("grid")}
                className={
                  viewMode === "grid"
                    ? "bg-purple-600 text-white hover:bg-purple-700"
                    : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"
                }
              >
                <Grip className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                onClick={() => setViewMode("list")}
                className={
                  viewMode === "list"
                    ? "bg-purple-600 text-white hover:bg-purple-700"
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
              className="flex-shrink-0"
              onClick={() => setError(null)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col justify-center items-center py-20">
            <Loader2 className="h-12 w-12 animate-spin text-purple-500 mb-4" />
            <span className="text-gray-600 font-medium">Đang tải danh sách danh tính...</span>
          </div>
        )}

        {/* Empty State */}
        {!loading && filtered.length === 0 && !error && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-purple-100 flex items-center justify-center mx-auto mb-4">
              <AppWindow className="w-10 h-10 text-purple-500" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {searchTerm ? "Không tìm thấy danh tính phù hợp" : "Chưa có danh tính nào"}
            </h3>
            <p className="text-gray-500 mb-6">
              {searchTerm
                ? "Thử điều chỉnh từ khóa tìm kiếm"
                : "Tạo danh tính đầu tiên để bắt đầu"}
            </p>
            {!searchTerm && (
              <Button 
                className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white"
                onClick={() => setCreateOpen(true)}
              >
                <Plus className="mr-2 h-5 w-5" />
                Tạo Danh tính mới
              </Button>
            )}
          </div>
        )}

        {/* Identity Grid/List */}
        {!loading && filtered.length > 0 && (
          <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
            {filtered.map((identity, index) => (
              <IdentityCard 
                key={identity.id || `identity-${index}`} 
                identity={identity} 
                onCopy={onCopy}
                onView={onView}
                onEdit={(i) => { 
                  setEditingIdentity(i); 
                  setEditOpen(true); 
                }}
                onDelete={onDelete}
                isDeleting={actionLoading === `delete-${identity.id}`}
                isCopying={actionLoading === `copy-${identity.id}`}
              />
            ))}
          </div>
        )}

        {/* Modals */}
        <IdentityDetailsModal 
          identity={selected} 
          open={open} 
          onClose={() => {
            setOpen(false);
            setSelected(null);
          }} 
        />
        
        <CreateIdentityModal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onCreated={(i) => {
            setIdentities((prev) => [i, ...prev]);
            setCreateOpen(false);
          }}
        />
        
        <CreateIdentityModal
          open={editOpen}
          onClose={() => {
            setEditOpen(false);
            setEditingIdentity(null);
          }}
          onCreated={(i) => {
            setIdentities((prev) => prev.map((p) => (p.id === i.id ? i : p)));
            setEditOpen(false);
            setEditingIdentity(null);
          }}
          mode="edit"
          initial={editingIdentity}
        />
      </div>
    </div>
  );
}