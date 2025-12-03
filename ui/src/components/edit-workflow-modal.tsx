"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { X } from "lucide-react";
import { type Procedure } from "@/lib/api";
import { useUpdateProcedureMutation } from "@/lib/queries";

export function EditWorkflowModal({ open, onClose, initial, onUpdated }: { open: boolean; onClose: () => void; initial: Procedure | null; onUpdated: (p: Procedure) => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const updateMutation = useUpdateProcedureMutation();

  useEffect(() => {
    if (!open) return;
    setError(null);
    setLoading(false);
    if (initial) {
      setTitle(initial.title || "");
      setDescription(initial.description || "");
    } else {
      setTitle("");
      setDescription("");
    }
  }, [open, initial]);

  const onSubmit = async () => {
    const t = title.trim();
    const d = description.trim();
    if (!t) { setError("Vui lòng nhập tên quy trình"); return; }
    if (!initial) return;
    try {
      setLoading(true);
      setError(null);
      const res = await updateMutation.mutateAsync({ id: initial.id, title: t, description: d });
      if (res) {
        onUpdated({ ...initial, title: res.title, description: res.description });
        onClose();
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Không thể cập nhật quy trình";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
        <div className="relative w-full max-w-3xl bg-white rounded-xl shadow-2xl my-8" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-black">Chỉnh sửa Quy trình</h2>
              <p className="text-gray-600 text-sm">Cập nhật tên và mô tả</p>
            </div>
            <Button variant="outline" size="icon" className="bg-white hover:bg-gray-100" onClick={onClose}>
              <X className="h-5 w-5" />
            </Button>
          </div>

          {error && (
            <div className="mx-6 mt-4 bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
              <p className="text-sm text-red-700 flex-1">{error}</p>
              <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          <div className="p-6 space-y-6">
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-700">Thông tin Quy trình</h3>
              </div>
              <div className="p-4 space-y-4">
                <div className="space-y-2">
                  <div className="text-sm">Tên quy trình *</div>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ví dụ: Tư vấn tuyển sinh" />
                </div>
                <div className="space-y-2">
                  <div className="text-sm">Mô tả</div>
                  <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-indigo-500 focus:ring-indigo-500" rows={6} />
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
            <Button variant="outline" className="bg-white" onClick={onClose}>Hủy</Button>
            <Button onClick={onSubmit} disabled={loading} className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white">Lưu thay đổi</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
