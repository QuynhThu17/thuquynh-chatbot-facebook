"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createIdentity, updateIdentity, type Identity } from "@/lib/api";

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
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-3xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-6 border-b">
            <div className="text-lg font-semibold">{mode === "edit" ? "Cập nhật nhận diện" : "Tạo nhận diện mới"}</div>
            <Button variant="outline" size="sm" className="bg-white" onClick={onClose}>Hủy</Button>
          </div>
          <div className="p-6 space-y-6">
            {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
            <div className="rounded-lg border p-4 space-y-4">
              <div className="text-sm font-semibold">Thông tin cơ bản</div>
              <div className="space-y-2">
                <div className="text-sm">Tên nhận diện *</div>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Ví dụ: Nhân viên tư vấn thân thiện" />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Thông tin *</div>
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm" rows={6} />
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
            <div className="rounded-lg border p-4 space-y-3">
              <div className="text-sm font-semibold">Ví dụ hội thoại</div>
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
            <div className="flex items-center justify-end">
              <Button onClick={onSubmit} disabled={loading} className="bg-blue-600 text-white">{mode === "edit" ? "Cập nhật" : "Tạo nhận diện"}</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}