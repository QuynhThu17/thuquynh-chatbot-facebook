"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createIdentity, updateIdentity, type Identity } from "@/lib/api";
import { X } from "lucide-react";

type Mode = "create" | "edit";

export function CreateIdentityModal({ open, onClose, onCreated, mode = "create", initial }: { open: boolean; onClose: () => void; onCreated: (i: Identity) => void; mode?: Mode; initial?: Identity | null }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [style, setStyle] = useState("");
  const [examples, setExamples] = useState<{ user: string; you: string }[]>([]);
  const [type, setType] = useState("custom");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setLoading(false);
    if (mode === "edit" && initial) {
      setTitle(initial.title || "");
      setDescription(initial.description || "");
      setStyle("");
      setExamples([]);
      setType("custom");
    } else {
      setTitle("");
      setDescription("");
      setStyle("");
      setExamples([]);
      setType("custom");
    }
  }, [open, mode, initial]);

  const addExample = () => {
    setExamples((prev) => [...prev, { user: "", you: "" }]);
  };

  const updateExample = (idx: number, key: "user" | "you", val: string) => {
    setExamples((prev) => prev.map((e, i) => (i === idx ? { ...e, [key]: val } : e)));
  };

  const onSubmit = async () => {
    const t = title.trim();
    const d = description.trim();
    const s = style.trim();
    if (!t || !d || !s) {
      setError("Vui lòng nhập đầy đủ Tên, Thông tin và Phong cách");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      if (mode === "edit" && initial) {
        const res = await updateIdentity(initial.id, { title: t, description: d, style: s, conversation_examples: examples });
        if (res?.success && res?.data) {
          onCreated(res.data);
          onClose();
        }
      } else {
        const res = await createIdentity({ title: t, description: d, style: s, conversation_examples: examples });
        if (res?.success && res?.data) {
          onCreated(res.data);
          onClose();
        }
      }
    } catch (e: any) {
      setError(e.message || "Không thể xử lý danh tính");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
        <div className="relative w-full max-w-4xl bg-white rounded-xl shadow-2xl my-8" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div>
              <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black">
                {mode === "edit" ? "Cập nhật danh tính" : "Tạo danh tính mới"}
              </h2>
              <p className="text-gray-600 text-sm">Định nghĩa phong cách và ví dụ hội thoại</p>
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

          <div className="p-6 space-y-6 max-h-[calc(100vh-280px)] overflow-y-auto">
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-700">Thông tin cơ bản</h3>
              </div>
              <div className="p-4 space-y-4">
                <div className="space-y-2">
                  <div className="text-sm">Tên nhận diện *</div>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ví dụ: Nhân viên tư vấn thân thiện" />
                </div>
                <div className="space-y-2">
                  <div className="text-sm">Thông tin *</div>
                  <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-blue-500 focus:ring-blue-500" rows={6} />
                  <div className="text-xs text-gray-500">{description.length}/2000 ký tự</div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm">Phong cách *</div>
                  <Input value={style} onChange={(e) => setStyle(e.target.value)} placeholder="Ví dụ: Thân thiện, Chuyên nghiệp" />
                </div>
                <div className="space-y-2">
                  <div className="text-sm">Loại</div>
                  <div className="flex items-center gap-2">
                    <button className={`px-3 py-1 rounded-full text-sm ${type === "default" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`} onClick={() => setType("default")}>default</button>
                    <button className={`px-3 py-1 rounded-full text-sm ${type === "custom" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-700"}`} onClick={() => setType("custom")}>custom</button>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                <h3 className="text-sm font-semibold text-gray-700">Ví dụ hội thoại</h3>
              </div>
              <div className="p-4 space-y-3">
                {examples.map((ex, idx) => (
                  <div key={idx} className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <Input value={ex.user} onChange={(e) => updateExample(idx, "user", e.target.value)} placeholder="User" />
                    <Input value={ex.you} onChange={(e) => updateExample(idx, "you", e.target.value)} placeholder="Bot" />
                  </div>
                ))}
                <div className="flex items-center">
                  <Button variant="outline" className="bg-white" onClick={addExample}>Thêm ví dụ khác</Button>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
            <Button variant="outline" className="bg-white" onClick={onClose}>Hủy</Button>
            <Button onClick={onSubmit} disabled={loading} className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white">{mode === "edit" ? "Cập nhật" : "Tạo nhận diện"}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
