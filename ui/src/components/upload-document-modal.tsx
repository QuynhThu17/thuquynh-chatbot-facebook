"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Upload } from "lucide-react";
import { uploadDocument, type KnowledgeDocument, getDocumentOptions } from "@/lib/api";

interface UploadDocumentModalProps {
  open: boolean;
  onClose: () => void;
  onUploaded: (doc: KnowledgeDocument) => void;
}

export function UploadDocumentModal({ open, onClose, onUploaded }: UploadDocumentModalProps) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allowedExtensions, setAllowedExtensions] = useState<string[]>([".pdf", ".doc", ".docx", ".xls", ".xlsx"]);

  const canSubmit = !!file && title.trim().length > 0 && !loading;

  // Fetch supported file types dynamically
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await getDocumentOptions();
        const data = res?.data || {};
        const adv: string[] = Array.isArray(data?.supported_file_types?.advanced) ? data.supported_file_types.advanced : [];
        const simple: string[] = Array.isArray(data?.supported_file_types?.simple) ? data.supported_file_types.simple : [];
        const exts = [...adv, ...simple].filter((e) => typeof e === "string" && e.startsWith("."));
        if (mounted && exts.length) setAllowedExtensions(exts);
      } catch {
        // Keep default allowedExtensions
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const onSubmit = async () => {
    if (!file) return;
    const ext = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;
    if (!allowedExtensions.includes(ext)) {
      setError(
        `Loại tệp chưa được hỗ trợ trong môi trường hiện tại. Vui lòng dùng một trong: ${allowedExtensions.join(", ")}.`
      );
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await uploadDocument({ file, title: title.trim(), company: company || undefined });
      if ((res as any)?.success && res.data) {
        onUploaded(res.data);
        onClose();
        // reset
        setTitle("");
        setCompany("");
        setFile(null);
      }
    } catch (err: any) {
      setError(err.message || "Tải lên thất bại");
    } finally {
      setLoading(false);
    }
  };

  return open ? (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-md bg-white rounded-xl border shadow-xl" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b">
            <div>
              <h2 className="text-lg font-semibold">Tải lên tài liệu</h2>
              <p className="mt-1 text-sm text-gray-600">Tải lên tài liệu để thêm vào cơ sở kiến thức của bạn</p>
            </div>
            <Button variant="outline" size="icon" className="bg-white" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Tên tài liệu <span className="text-red-500">*</span></label>
              <Input placeholder="Nhập tên tài liệu" value={title} onChange={(e) => setTitle(e.target.value)} className="bg-white" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Công ty</label>
              <Select value={company} onValueChange={(v) => setCompany(v === "none" ? "" : v)}>
                <SelectTrigger className="bg-white">
                  <SelectValue placeholder="Chọn công ty" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Không chọn</SelectItem>
                  <SelectItem value="company_a">Company A</SelectItem>
                  <SelectItem value="company_b">Company B</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Tệp <span className="text-red-500">*</span></label>
              <input
                type="file"
                accept={allowedExtensions.join(",")}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full rounded-md border border-gray-300 p-2"
              />
            </div>

            {error && <div className="text-sm text-red-600">{error}</div>}

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button variant="outline" className="bg-white" onClick={onClose}>Hủy</Button>
              <Button disabled={!canSubmit} onClick={onSubmit} className="bg-blue-600 hover:bg-blue-700 text-white">
                <Upload className="h-4 w-4" />
                Tải lên
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  ) : null;
}