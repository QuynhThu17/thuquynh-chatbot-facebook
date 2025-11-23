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
} from "lucide-react";
import { type Procedure, getProcedures, updateProcedure, deleteProcedure, copyProcedure } from "@/lib/api";
import { WorkflowDetailsModal } from "@/components/workflow-details-modal";
function WorkflowCard({
  workflow,
  editing,
  setEditing,
  onSave,
  onCopy,
  onDelete,
  onView,
}: {
  workflow: Procedure;
  editing: { id: Procedure["id"] | null; title: string; description: string };
  setEditing: (e: { id: Procedure["id"] | null; title: string; description: string }) => void;
  onSave: (id: Procedure["id"], title: string, description: string) => Promise<void>;
  onCopy: (id: Procedure["id"]) => Promise<void>;
  onDelete: (id: Procedure["id"]) => Promise<void>;
  onView: (w: Procedure) => void;
}) {
  return (
    <Card className="flex flex-col bg-white text-black border border-gray-200">
      <CardHeader>
        {editing.id === workflow.id ? (
          <div className="flex items-center gap-2 w-full">
            <Input
              value={editing.title}
              onChange={(e) => setEditing({ ...editing, title: e.target.value })}
              className="text-base font-bold"
            />
            <Button variant="ghost" size="icon" onClick={() => onSave(workflow.id, editing.title, editing.description)}>
              <Check className="w-5 h-5 text-green-600" />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => setEditing({ id: null, title: "", description: "" })}>
              <X className="w-5 h-5 text-gray-600" />
            </Button>
          </div>
        ) : (
          <CardTitle className="text-base font-bold text-gray-900">
            {workflow.title}
          </CardTitle>
        )}
      </CardHeader>
      <CardContent className="flex-grow">
        {editing.id === workflow.id ? (
          <textarea
            value={editing.description}
            onChange={(e) => setEditing({ ...editing, description: e.target.value })}
            className="w-full rounded-md border border-gray-300 p-2 text-sm text-gray-700"
            rows={4}
          />
        ) : (
          <p className="text-sm text-gray-700 line-clamp-2 break-words">
            {workflow.description}
          </p>
        )}
        {workflow.type && <p className="text-sm text-gray-500 mt-2">{workflow.type}</p>}
      </CardContent>
      <div className="flex items-center justify-end p-4 border-t">
        <Button
          variant="outline"
          size="sm"
          className="flex items-center gap-2 bg-white"
          onClick={() => onView(workflow)}
        >
          <Eye className="h-4 w-4" />
          Xem
        </Button>
        <Button variant="ghost" size="icon">
          <AppWindow className="w-5 h-5" />
        </Button>
        {editing.id === workflow.id ? null : (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setEditing({ id: workflow.id, title: workflow.title, description: workflow.description || "" })}
            aria-label="Sửa quy trình"
          >
            <Edit className="w-5 h-5" />
          </Button>
        )}
        <Button variant="ghost" size="icon" onClick={() => onCopy(workflow.id)} aria-label="Sao chép quy trình">
          <Copy className="w-5 h-5" />
        </Button>
        <Button variant="ghost" size="icon" className="text-red-600" onClick={() => onDelete(workflow.id)} aria-label="Xóa quy trình">
          <Trash2 className="w-5 h-5" />
        </Button>
      </div>
    </Card>
  );
}

export default function WorkflowPage() {
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [editing, setEditing] = useState<{ id: Procedure["id"] | null; title: string; description: string }>({ id: null, title: "", description: "" });
  const [selected, setSelected] = useState<Procedure | null>(null);
  const [open, setOpen] = useState<boolean>(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getProcedures();
        if (res.success) {
          setProcedures(res.data || []);
        } else {
          setError(res.message || "Không thể tải danh sách quy trình");
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
    if (!term) return procedures;
    return procedures.filter((w) => `${w.title} ${w.description || ""}`.toLowerCase().includes(term));
  }, [procedures, searchTerm]);

  const onSave = async (id: Procedure["id"], title: string, description: string) => {
    try {
      const res = await updateProcedure(id, { title, description });
      if (res?.success && res?.data) {
        setProcedures((prev) => prev.map((p) => (p.id === id ? { ...p, title: res.data.title, description: res.data.description } : p)));
        setEditing({ id: null, title: "", description: "" });
      }
    } catch (err) {
      console.error("Update procedure failed", err);
    }
  };

  const onCopy = async (id: Procedure["id"]) => {
    try {
      const res = await copyProcedure(id);
      if (res?.success && res?.data) {
        setProcedures((prev) => [res.data, ...prev]);
      }
    } catch (err) {
      console.error("Copy procedure failed", err);
    }
  };

  const onDelete = async (id: Procedure["id"]) => {
    try {
      const res = await deleteProcedure(id);
      if (res?.success !== false) {
        setProcedures((prev) => prev.filter((p) => p.id !== id));
        if (editing.id === id) setEditing({ id: null, title: "", description: "" });
      }
    } catch (err) {
      console.error("Delete procedure failed", err);
    }
  };

  const onView = (w: Procedure) => {
    setSelected(w);
    setOpen(true);
  };

  return (
    <div className="p-8">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white text-black border border-gray-200">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">Tổng số quy trình</CardTitle>
            <Workflow className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">{procedures.length}</div>
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-between items-center mb-6">
        <div className="relative w-1/3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            placeholder="Tìm kiếm quy trình..."
            className="pl-10"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="icon">
            <Grip className="w-5 h-5" />
          </Button>
          <Button variant="ghost" size="icon">
            <List className="w-5 h-5" />
          </Button>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white">
            <Plus className="w-5 h-5 mr-2" />
            Tạo quy trình
          </Button>
        </div>
      </div>

      {error && <div className="mb-6 text-sm text-red-600">{error}</div>}

      {loading ? (
        <div className="text-gray-600">Đang tải...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((workflow, index) => (
            <WorkflowCard
              key={workflow.id || `workflow-${index}`}
              workflow={workflow}
              editing={editing}
              setEditing={setEditing}
              onSave={onSave}
              onCopy={onCopy}
              onDelete={onDelete}
              onView={onView}
            />
          ))}
        </div>
      )}
      <WorkflowDetailsModal workflow={selected} open={open} onClose={() => setOpen(false)} />
    </div>
  );
}