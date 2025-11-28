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
  Check,
  X,
  Eye,
  Plus,
  Search,
  Trash2,
  Workflow,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { type Procedure } from "@/lib/api";
import { useProceduresQuery, useCopyProcedureMutation, useDeleteProcedureMutation } from "@/lib/queries";
import { WorkflowDetailsModal } from "@/components/workflow-details-modal";
import { CreateProcedureModal } from "@/components/create-procedure-modal";
import { EditWorkflowModal } from "@/components/edit-workflow-modal";

function WorkflowCard({
  workflow,
  onEdit,
  onCopy,
  onDelete,
  onView,
  isDeleting,
  isCopying,
}: {
  workflow: Procedure;
  onEdit: (w: Procedure) => void;
  onCopy: (id: Procedure["id"]) => Promise<void>;
  onDelete: (id: Procedure["id"]) => Promise<void>;
  onView: (w: Procedure) => void;
  isDeleting: boolean;
  isCopying: boolean;
}) {

  return (
    <Card className="flex flex-col bg-white border border-gray-200 hover:shadow-lg transition-all duration-200 hover:border-indigo-300">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base font-bold text-gray-900 flex-1">
            {workflow.title}
          </CardTitle>
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-md">
            <Workflow className="w-5 h-5 text-white" />
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-grow space-y-3">
        <>
          <p className="text-sm text-gray-700 line-clamp-3 leading-relaxed">
            {workflow.description || "Chưa có mô tả"}
          </p>
          {workflow.type && (
            <div className="inline-flex items-center px-3 py-1 rounded-lg bg-indigo-50 border border-indigo-100">
              <span className="text-xs font-medium text-indigo-700">{workflow.type}</span>
            </div>
          )}
        </>
      </CardContent>

      <div className="flex items-center justify-end gap-1 p-3 border-t border-gray-100">
        <>
          <Button
            variant="outline"
            size="sm"
            className="bg-white text-black hover:bg-blue-50 hover:text-blue-600 hover:border-blue-300"
            onClick={() => onView(workflow)}
          >
            <Eye className="h-4 w-4 mr-1.5" />
            <span className="hidden sm:inline">Xem</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="hover:bg-purple-50 text-black hover:text-purple-600"
            onClick={() => onEdit(workflow)}
            disabled={isDeleting || isCopying}
          >
            <Edit className="w-4 h-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            className="hover:bg-green-50 text-black hover:text-green-600"
            onClick={() => onCopy(workflow.id)}
            disabled={isDeleting || isCopying}
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
            className="hover:bg-red-50 text-black hover:text-red-600"
            onClick={() => onDelete(workflow.id)}
            disabled={isDeleting || isCopying}
          >
            {isDeleting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Trash2 className="w-4 h-4" />
            )}
          </Button>
        </>
      </div>
    </Card>
  );
}

export default function WorkflowPage() {
  const proceduresQuery = useProceduresQuery();
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const loading = proceduresQuery.isLoading && procedures.length === 0;
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selected, setSelected] = useState<Procedure | null>(null);
  const [open, setOpen] = useState<boolean>(false);
  const [createOpen, setCreateOpen] = useState<boolean>(false);
  const [editOpen, setEditOpen] = useState<boolean>(false);
  const [editingProc, setEditingProc] = useState<Procedure | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    const rows = proceduresQuery.data as Procedure[] | undefined;
    if (Array.isArray(rows)) setProcedures(rows);
    const err = proceduresQuery.error as any;
    if (err && !error) setError(err?.message || "Không thể tải danh sách quy trình");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proceduresQuery.data, proceduresQuery.error]);

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return procedures;
    return procedures.filter((w) => 
      `${w.title} ${w.description || ""}`.toLowerCase().includes(term)
    );
  }, [procedures, searchTerm]);

  const onStartEdit = (w: Procedure) => {
    setEditingProc(w);
    setEditOpen(true);
  };

  const copyMutation = useCopyProcedureMutation();
  const onCopy = async (id: Procedure["id"]) => {
    const actionKey = `copy-${id}`;
    setActionLoading(actionKey);
    try {
      const created = await copyMutation.mutateAsync(id);
      if (created) setProcedures((prev) => [created, ...prev]);
    } catch (err: any) {
      setError(err?.message || "Không thể sao chép quy trình");
    } finally {
      setActionLoading(null);
    }
  };

  const deleteMutation = useDeleteProcedureMutation();
  const onDelete = async (id: Procedure["id"]) => {
    const workflow = procedures.find(p => p.id === id);
    if (!confirm(`Bạn có chắc chắn muốn xóa quy trình "${workflow?.title}"?`)) return;

    const actionKey = `delete-${id}`;
    setActionLoading(actionKey);
    try {
      await deleteMutation.mutateAsync(id);
      setProcedures((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      setError(err?.message || "Không thể xóa quy trình");
    } finally {
      setActionLoading(null);
    }
  };

  const onView = (w: Procedure) => {
    setSelected(w);
    setOpen(true);
  };

  return (
    <div className="min-h-screen bg-white p-6">
      <div>
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-black mb-2">
              Quản lý Quy trình
            </h1>
            <p className="text-gray-600">Tạo và quản lý quy trình làm việc cho bot của bạn</p>
          </div>
          <Button 
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="mr-2 h-5 w-5" />
            Tạo quy trình
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                Tổng số quy trình
              </CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 flex items-center justify-center shadow-md">
                <Workflow className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{procedures.length}</div>
              <p className="text-xs text-gray-500 mt-1">Quy trình đã tạo</p>
            </CardContent>
          </Card>

          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                Đang chỉnh sửa
              </CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-md">
                <Edit className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{editOpen ? 1 : 0}</div>
              <p className="text-xs text-gray-500 mt-1">Quy trình đang edit</p>
            </CardContent>
          </Card>

          <Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                Kết quả tìm kiếm
              </CardTitle>
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <Search className="h-5 w-5 text-white" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900">{filtered.length}</div>
              <p className="text-xs text-gray-500 mt-1">Quy trình phù hợp</p>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <Input
                placeholder="Tìm kiếm quy trình..."
                className="pl-10 border-gray-300 focus:border-indigo-500 focus:ring-indigo-500"
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
                    ? "bg-indigo-600 text-white hover:bg-indigo-700"
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
                    ? "bg-indigo-600 text-white hover:bg-indigo-700"
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
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
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
            <Loader2 className="h-12 w-12 animate-spin text-indigo-500 mb-4" />
            <span className="text-gray-600 font-medium">Đang tải danh sách quy trình...</span>
          </div>
        )}

        {/* Empty State */}
        {!loading && filtered.length === 0 && !error && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-indigo-100 flex items-center justify-center mx-auto mb-4">
              <Workflow className="w-10 h-10 text-indigo-500" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {searchTerm ? "Không tìm thấy quy trình phù hợp" : "Chưa có quy trình nào"}
            </h3>
            <p className="text-gray-500 mb-6">
              {searchTerm
                ? "Thử điều chỉnh từ khóa tìm kiếm"
                : "Tạo quy trình đầu tiên để bắt đầu"}
            </p>
            {!searchTerm && (
              <Button 
                className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white"
                onClick={() => setCreateOpen(true)}
              >
                <Plus className="mr-2 h-5 w-5" />
                Tạo quy trình mới
              </Button>
            )}
          </div>
        )}

        {/* Workflow Grid/List */}
        {!loading && filtered.length > 0 && (
          <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
            {filtered.map((workflow, index) => (
              <WorkflowCard
                key={workflow.id || `workflow-${index}`}
                workflow={workflow}
                onEdit={onStartEdit}
                onCopy={onCopy}
                onDelete={onDelete}
                onView={onView}
                isDeleting={actionLoading === `delete-${workflow.id}`}
                isCopying={actionLoading === `copy-${workflow.id}`}
              />
            ))}
          </div>
        )}

        {/* Modals */}
        <WorkflowDetailsModal 
          workflow={selected} 
          open={open} 
          onClose={() => {
            setOpen(false);
            setSelected(null);
          }} 
        />
        
        <CreateProcedureModal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onCreated={(p) => {
            setProcedures((prev) => [p, ...prev]);
            setCreateOpen(false);
          }}
        />

        <EditWorkflowModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          initial={editingProc}
          onUpdated={(p) => {
            setProcedures((prev) => prev.map((x) => x.id === p.id ? { ...x, title: p.title, description: p.description } : x));
            setEditOpen(false);
            setEditingProc(null);
          }}
        />
      </div>
    </div>
  );
}
