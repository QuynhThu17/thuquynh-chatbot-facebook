"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateBot, type Bot, type KnowledgeDocument, getBotKnowledge, getDocuments, setBotKnowledge } from "@/lib/api";

export function EditBotModal({ open, onClose, bot, onUpdated }: { open: boolean; onClose: () => void; bot: Bot; onUpdated: (b: Bot) => void }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [target, setTarget] = useState("");
  const [mission, setMission] = useState("");
  const [note, setNote] = useState("");
  const [language, setLanguage] = useState("");
  const [typeValue, setTypeValue] = useState<string>("");
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [allDocs, setAllDocs] = useState<KnowledgeDocument[]>([]);
  const [pickerSearch, setPickerSearch] = useState("");
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
    setTypeValue(bot?.type || "");
    setError(null);
    setLoading(false);
    const run = async () => {
      try {
        const bk = await getBotKnowledge(bot.id);
        const rows = Array.isArray((bk as any)?.data?.documents) ? (bk as any).data.documents : [];
        const mapped = rows.map((d: any) => ({ id: d?.document_id ?? d?.id ?? d?._id ?? d?.uuid, title: d?.document_name || d?.file_name || "Tài liệu" }));
        setKnowledgeDocs(mapped as any);
      } catch {}
      try {
        const dk = await getDocuments();
        setAllDocs(dk?.data || []);
      } catch {}
    };
    run();
  }, [open, bot]);

  const onSubmit = async () => {
    const payload: any = {
      name: name.trim(),
      role: role.trim(),
      target: target.trim(),
      mission: mission.trim(),
      note: note.trim(),
      language_code: language.trim(),
      type: typeValue || undefined,
      knowledge: knowledgeDocs.map((d) => d.id),
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
              <div className="space-y-2">
                <div className="text-sm">Loại</div>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => setTypeValue("default")} className={`inline-flex items-center rounded-full border px-3 py-1 text-sm ${typeValue === "default" ? "bg-blue-600 text-white border-blue-600" : "bg-gray-50 text-gray-800"}`}>Mặc định</button>
                  <button type="button" onClick={() => setTypeValue("custom")} className={`inline-flex items-center rounded-full border px-3 py-1 text-sm ${typeValue === "custom" ? "bg-blue-600 text-white border-blue-600" : "bg-gray-50 text-gray-800"}`}>Tùy chỉnh</button>
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-sm">Kiến thức</div>
                <div className="flex flex-wrap gap-2">
                  {knowledgeDocs.map((d, i) => (
                    <span key={`kd-${i}`} className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm bg-blue-600 text-white">
                      {d.title || String(d.id)}
                      <button type="button" className="ml-1 rounded-full bg-white/20 px-1" onClick={async () => { try { await setBotKnowledge(bot.id, knowledgeDocs.filter((x) => String(x.id) !== String(d.id)).map((x) => x.id)); setKnowledgeDocs((prev) => prev.filter((x) => String(x.id) !== String(d.id))); } catch {} }}>×</button>
                    </span>
                  ))}
                  {knowledgeDocs.length === 0 && (
                    <span className="inline-flex items-center rounded-full border px-3 py-1 text-sm bg-gray-50 text-gray-600">Chưa chọn</span>
                  )}
                </div>
                <div>
                  <Button variant="outline" className="bg-white" onClick={() => setPickerOpen(true)}>Chọn kiến thức</Button>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-end">
              <Button onClick={onSubmit} disabled={loading} className="bg-blue-600 text-white">Cập nhật Bot</Button>
            </div>
          </div>
        </div>
      </div>
      {pickerOpen && (
        <KnowledgePicker
          open={pickerOpen}
          onClose={() => setPickerOpen(false)}
          allDocs={allDocs}
          selected={knowledgeDocs.map((d) => d.id)}
          onConfirm={async (ids) => {
            const mapById: Record<string, KnowledgeDocument> = {};
            for (const d of allDocs) mapById[String(d.id)] = d;
            const next = ids.map((id) => mapById[String(id)] || ({ id, title: String(id) } as any));
            try {
              await setBotKnowledge(bot.id, ids as any);
              setKnowledgeDocs(next);
            } catch {}
            setPickerOpen(false);
          }}
        />
      )}
    </div>
  );
}

function KnowledgePicker({ open, onClose, allDocs, selected, onConfirm }: { open: boolean; onClose: () => void; allDocs: KnowledgeDocument[]; selected: Array<string | number>; onConfirm: (ids: Array<string | number>) => void }) {
  const [search, setSearch] = useState("");
  const [current, setCurrent] = useState<Array<string | number>>(selected);
  useEffect(() => {
    if (open) setCurrent(selected);
  }, [open, selected]);
  const filtered = allDocs.filter((d) => (d.title || "").toLowerCase().includes(search.trim().toLowerCase()));
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-2xl bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-4 border-b">
            <div className="font-semibold">Chọn kiến thức</div>
            <Button variant="outline" size="sm" className="bg-white" onClick={onClose}>Đóng</Button>
          </div>
          <div className="p-4 space-y-4">
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tìm kiếm..." className="w-full border rounded-md px-3 py-2 text-sm" />
            <div className="max-h-[360px] overflow-y-auto space-y-2">
              {filtered.map((d) => {
                const checked = current.some((id) => String(id) === String(d.id));
                return (
                  <label key={String(d.id)} className="flex items-center justify-between border rounded-md px-3 py-2">
                    <div className="text-sm text-gray-800">{d.title || String(d.id)}</div>
                    <input type="checkbox" checked={checked} onChange={(e) => {
                      if (e.target.checked) setCurrent((prev) => [...prev, d.id]); else setCurrent((prev) => prev.filter((x) => String(x) !== String(d.id)));
                    }} />
                  </label>
                );
              })}
              {filtered.length === 0 && <div className="text-sm text-gray-600">Không có tài liệu</div>}
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" className="bg-white" onClick={onClose}>Hủy</Button>
              <Button className="bg-blue-600 text-white" onClick={() => onConfirm(current)}>Xác nhận</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}