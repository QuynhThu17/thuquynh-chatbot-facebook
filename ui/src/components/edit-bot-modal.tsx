"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateBot, type Bot } from "@/lib/api";

export function EditBotModal({ open, onClose, bot, onUpdated }: { open: boolean; onClose: () => void; bot: Bot; onUpdated: (b: Bot) => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [target, setTarget] = useState("");
  const [mission, setMission] = useState("");
  const [note, setNote] = useState("");
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(bot?.name || "");
    setRole(bot?.role || "");
    setTarget(bot?.target || "");
    setMission(bot?.mission || "");
    setNote(bot?.note || "");
    setLanguage(bot?.language_code || "");
    setError(null);
    setLoading(false);
  }, [open, bot]);

  const onSubmit = async () => {
    const payload: any = {
      name: name.trim(),
      role: role.trim(),
      target: target.trim(),
      mission: mission.trim(),
      note: note.trim(),
      language_code: language.trim(),
    };
    try {
      setLoading(true);
      const res = await updateBot(bot.id, payload);
      if (res?.success && res?.data) {
        onUpdated(res.data);
        onClose();
      }
    } catch (e: any) {
      setError(e.message || "Không thể cập nhật bot");
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
            <div className="text-lg font-semibold">Chỉnh sửa cấu hình</div>
            <Button variant="outline" size="sm" className="bg-white" onClick={onClose}>Hủy</Button>
          </div>
          <div className="p-6 space-y-6">
            {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
            <div className="rounded-lg border p-4 space-y-4">
              <div className="space-y-2">
                <div className="text-sm">Tên bot</div>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên bot" />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Vai trò</div>
                <textarea value={role} onChange={(e) => setRole(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm" rows={4} />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Mục tiêu</div>
                <textarea value={target} onChange={(e) => setTarget(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm" rows={3} />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Nhiệm vụ</div>
                <textarea value={mission} onChange={(e) => setMission(e.target.value)} className="w-full rounded-md border border-gray-300 p-2 text-sm" rows={4} />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Ghi chú</div>
                <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ghi chú" />
              </div>
              <div className="space-y-2">
                <div className="text-sm">Ngôn ngữ</div>
                <Input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="vi, en" />
              </div>
            </div>
            <div className="flex items-center justify-end">
              <Button onClick={onSubmit} disabled={loading} className="bg-blue-600 text-white">Cập nhật Bot</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}