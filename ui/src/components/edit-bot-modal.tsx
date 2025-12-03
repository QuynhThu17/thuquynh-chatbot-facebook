"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { updateBot, type Bot, type KnowledgeDocument, getBotKnowledge, getDocuments, setBotKnowledge } from "@/lib/api";
import { X, Loader2, Search, FileText, AlertCircle, Check } from "lucide-react";

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
  const [loading, setLoading] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [removingDoc, setRemovingDoc] = useState<string | number | null>(null);

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
    
    const fetchData = async () => {
      setLoadingData(true);
      try {
        // Fetch bot knowledge
        const bk = await getBotKnowledge(bot.id);
        const rows = Array.isArray((bk as any)?.data?.documents) ? (bk as any).data.documents : [];
        const mapped = rows.map((d: any) => ({ 
          id: d?.document_id ?? d?.id ?? d?._id ?? d?.uuid, 
          title: d?.document_name || d?.file_name || "Tài liệu" 
        }));
        setKnowledgeDocs(mapped as any);

        // Fetch all documents
        const dk = await getDocuments();
        setAllDocs(dk?.data || []);
      } catch (err: any) {
        setError(err?.message || "Không thể tải dữ liệu");
      } finally {
        setLoadingData(false);
      }
    };
    
    fetchData();
  }, [open, bot]);

  const handleRemoveKnowledge = async (doc: KnowledgeDocument) => {
    setRemovingDoc(doc.id);
    try {
      const remaining = knowledgeDocs.filter((x) => String(x.id) !== String(doc.id));
      await setBotKnowledge(bot.id, remaining.map((x) => x.id));
      setKnowledgeDocs(remaining);
    } catch (err: any) {
      setError(err?.message || "Không thể xóa tài liệu");
    } finally {
      setRemovingDoc(null);
    }
  };

  const onSubmit = async () => {
    if (!name.trim()) {
      setError("Vui lòng nhập tên bot");
      return;
    }

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
      setError(null);
      const res = await updateBot(bot.id, payload);
      if (res?.success && res?.data) {
        onUpdated(res.data);
        onClose();
      } else {
        setError(res?.message || "Không thể cập nhật bot");
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
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
        <div className="relative w-full max-w-3xl bg-white rounded-xl shadow-2xl my-8" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">Chỉnh sửa Bot</h2>
                <p className="text-sm text-gray-500">Cập nhật cấu hình cho {bot?.name}</p>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="icon" 
              className="bg-white hover:bg-gray-100"
              onClick={onClose}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6 max-h-[calc(100vh-220px)] overflow-y-auto">
            {/* Error Message */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-red-700 font-medium">{error}</p>
                </div>
                <button 
                  onClick={() => setError(null)}
                  className="text-red-500 hover:text-red-700"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            {loadingData ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500 mb-2" />
                <span className="text-sm text-gray-500">Đang tải dữ liệu...</span>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Basic Info Section */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <h3 className="text-sm font-semibold text-gray-700">Thông tin cơ bản</h3>
                  </div>
                  <div className="p-4 space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">
                        Tên bot <span className="text-red-500">*</span>
                      </label>
                      <Input 
                        value={name} 
                        onChange={(e) => setName(e.target.value)} 
                        placeholder="Nhập tên bot..." 
                        className="border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-gray-700">Ngôn ngữ</label>
                        <Input 
                          value={language} 
                          onChange={(e) => setLanguage(e.target.value)} 
                          placeholder="vi, en, ..." 
                          className="border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-sm font-medium text-gray-700">Loại</label>
                        <div className="flex items-center gap-2">
                          <button 
                            type="button" 
                            onClick={() => setTypeValue("default")} 
                            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                              typeValue === "default" 
                                ? "bg-blue-600 text-white" 
                                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                            }`}
                          >
                            Mặc định
                          </button>
                          <button 
                            type="button" 
                            onClick={() => setTypeValue("custom")} 
                            className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                              typeValue === "custom" 
                                ? "bg-blue-600 text-white" 
                                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                            }`}
                          >
                            Tùy chỉnh
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Configuration Section */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <h3 className="text-sm font-semibold text-gray-700">Cấu hình chi tiết</h3>
                  </div>
                  <div className="p-4 space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">Vai trò</label>
                      <textarea 
                        value={role} 
                        onChange={(e) => setRole(e.target.value)} 
                        className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none" 
                        rows={4}
                        placeholder="Mô tả vai trò của bot..."
                      />
                      <p className="text-xs text-gray-500">Mỗi dòng sẽ là một điểm trong danh sách vai trò</p>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">Mục tiêu</label>
                      <textarea 
                        value={target} 
                        onChange={(e) => setTarget(e.target.value)} 
                        className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none" 
                        rows={3}
                        placeholder="Mô tả mục tiêu của bot..."
                      />
                      <p className="text-xs text-gray-500">Mỗi dòng sẽ là một điểm trong danh sách mục tiêu</p>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">Nhiệm vụ</label>
                      <textarea 
                        value={mission} 
                        onChange={(e) => setMission(e.target.value)} 
                        className="w-full rounded-lg border border-gray-300 p-3 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none" 
                        rows={4}
                        placeholder="Mô tả nhiệm vụ của bot..."
                      />
                      <p className="text-xs text-gray-500">Mỗi dòng sẽ là một điểm trong danh sách nhiệm vụ</p>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700">Ghi chú</label>
                      <Input 
                        value={note} 
                        onChange={(e) => setNote(e.target.value)} 
                        placeholder="Thêm ghi chú..." 
                        className="border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                  </div>
                </div>

                {/* Knowledge Section */}
                <div className="bg-white rounded-lg border border-gray-200">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-700">Tài liệu kiến thức</h3>
                      <span className="text-xs text-gray-500">{knowledgeDocs.length} tài liệu</span>
                    </div>
                  </div>
                  <div className="p-4 space-y-4">
                    {knowledgeDocs.length > 0 ? (
                      <div className="space-y-2">
                        {knowledgeDocs.map((d, i) => (
                          <div 
                            key={`kd-${i}`}
                            className="flex items-center justify-between gap-3 p-3 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors"
                          >
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />
                              <span className="text-sm text-gray-900 truncate">{d.title || String(d.id)}</span>
                            </div>
                            <button
                              type="button"
                              disabled={removingDoc === d.id}
                              className="p-1.5 rounded-lg hover:bg-red-100 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                              onClick={() => handleRemoveKnowledge(d)}
                            >
                              {removingDoc === d.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <X className="w-4 h-4" />
                              )}
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                        <p className="text-sm text-gray-500">Chưa có tài liệu kiến thức nào</p>
                      </div>
                    )}
                    
                    <Button 
                      variant="outline" 
                      className="w-full bg-white hover:bg-gray-50"
                      onClick={() => setPickerOpen(true)}
                    >
                      <FileText className="w-4 h-4 mr-2" />
                      Thêm tài liệu kiến thức
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-200 bg-gray-50">
            <Button 
              variant="outline" 
              className="bg-white hover:bg-gray-100"
              onClick={onClose}
              disabled={loading}
            >
              Hủy
            </Button>
            <Button 
              onClick={onSubmit} 
              disabled={loading || loadingData}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Đang cập nhật...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Cập nhật Bot
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Knowledge Picker Modal */}
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
            } catch (err: any) {
              setError(err?.message || "Không thể cập nhật kiến thức");
            }
            setPickerOpen(false);
          }}
        />
      )}
    </div>
  );
}

function KnowledgePicker({ 
  open, 
  onClose, 
  allDocs, 
  selected, 
  onConfirm 
}: { 
  open: boolean; 
  onClose: () => void; 
  allDocs: KnowledgeDocument[]; 
  selected: Array<string | number>; 
  onConfirm: (ids: Array<string | number>) => void 
}) {
  const [search, setSearch] = useState("");
  const [current, setCurrent] = useState<Array<string | number>>(selected);

  useEffect(() => {
    if (open) setCurrent(selected);
  }, [open, selected]);

  const filtered = allDocs.filter((d) => 
    (d.title || "").toLowerCase().includes(search.trim().toLowerCase())
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60]">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-4 sm:p-6">
        <div className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl my-8" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Chọn tài liệu kiến thức</h3>
                <p className="text-sm text-gray-500">{current.length} đã chọn</p>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="icon" 
              className="bg-white hover:bg-gray-100"
              onClick={onClose}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input 
                value={search} 
                onChange={(e) => setSearch(e.target.value)} 
                placeholder="Tìm kiếm tài liệu..." 
                className="w-full border border-gray-300 rounded-lg pl-10 pr-4 py-2.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500" 
              />
            </div>

            {/* Documents List */}
            <div className="max-h-[400px] overflow-y-auto space-y-2 pr-2">
              {filtered.length > 0 ? (
                filtered.map((d) => {
                  const checked = current.some((id) => String(id) === String(d.id));
                  return (
                    <label 
                      key={String(d.id)} 
                      className={`flex items-center justify-between gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                        checked 
                          ? 'border-blue-500 bg-blue-50' 
                          : 'border-gray-200 bg-white hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <FileText className={`w-4 h-4 flex-shrink-0 ${checked ? 'text-blue-600' : 'text-gray-400'}`} />
                        <span className={`text-sm truncate ${checked ? 'text-blue-900 font-medium' : 'text-gray-700'}`}>
                          {d.title || String(d.id)}
                        </span>
                      </div>
                      <input 
                        type="checkbox" 
                        checked={checked} 
                        onChange={(e) => {
                          if (e.target.checked) {
                            setCurrent((prev) => [...prev, d.id]);
                          } else {
                            setCurrent((prev) => prev.filter((x) => String(x) !== String(d.id)));
                          }
                        }}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                    </label>
                  );
                })
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">
                    {search ? "Không tìm thấy tài liệu phù hợp" : "Chưa có tài liệu nào"}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
            <span className="text-sm text-gray-600">
              Đã chọn: <span className="font-semibold text-gray-900">{current.length}</span> tài liệu
            </span>
            <div className="flex items-center gap-3">
              <Button 
                variant="outline" 
                className="bg-white hover:bg-gray-100"
                onClick={onClose}
              >
                Hủy
              </Button>
              <Button 
                className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                onClick={() => onConfirm(current)}
              >
                <Check className="w-4 h-4 mr-2" />
                Xác nhận
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}