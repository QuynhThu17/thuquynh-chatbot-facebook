"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createProcedure, type Procedure } from "@/lib/api";

export function CreateProcedureModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (p: Procedure) => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("custom");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDescription("");
    setType("custom");
    setError(null);
    setLoading(false);
  }, [open]);

  const onSubmit = async () => {
    const t = title.trim();
    const d = description.trim();
    if (!t || !d) {
      setError("Vui lòng nhập đầy đủ tên và quy trình");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await createProcedure({ title: t, description: d, type });
      if (res?.success && res?.data) {
        onCreated(res.data);
        onClose();
      }
    } catch (e: any) {
      setError(e.message || "Không thể tạo quy trình");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-3xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-6 border-b">
            <div className="text-lg font-semibold">Tạo Quy trình mới</div>
            <Button variant="outline" size="sm" className="bg-white" onClick={onClose}>Hủy</Button>
          </div>
          <div className="p-6 space-y-6">
            {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
            <div className="rounded-lg border p-4 space-y-4">
              <div className="text-sm font-semibold">Thông tin cơ bản</div>
              <div className="space-y-2">
                <div className="text-sm">Tên Quy trình *</div>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Tên quy trình" />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Quy trình *</div>
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm" rows={8} />
                <div className="text-xs text-gray-500">{description.length}/500 ký tự</div>
              </div>
              <div className="space-y-2">
                <div className="text-sm">Loại</div>
                <div className="flex items-center gap-2">
                  <button className={`px-3 py-1 rounded-full text-sm ${type === "default" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`} onClick={() => setType("default")}>default</button>
                  <button className={`px-3 py-1 rounded-full text-sm ${type === "custom" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`} onClick={() => setType("custom")}>custom</button>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end">
              <Button onClick={onSubmit} disabled={loading} className="bg-blue-600 text-white">Tạo Quy trình</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}