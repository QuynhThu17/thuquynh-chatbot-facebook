"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Grid3x3,
  List,
  Search,
  Upload,
  FileText,
  BrainCircuit,
  Trash2,
  Loader2,
  AlertCircle,
  Plus,
  File,
  Clock,
} from "lucide-react";
import { UploadDocumentModal } from "@/components/upload-document-modal";
import {
  type KnowledgeDocument,
  getDocuments,
  deleteDocument,
} from "@/lib/api";

function DocumentCard({
  doc,
  index,
  onDelete,
}: {
  doc: KnowledgeDocument;
  index: number;
  onDelete: (doc: KnowledgeDocument) => void;
}) {
  const isProcessed = (doc.status || "").toLowerCase().includes("xử lý");
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    await onDelete(doc);
    setDeleting(false);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-all duration-200 hover:border-blue-300">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 flex-1">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold shadow-md ${
            isProcessed ? 'bg-gradient-to-br from-green-500 to-green-600' : 'bg-gradient-to-br from-yellow-500 to-yellow-600'
          }`}>
            <File className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 whitespace-normal">
              {doc.title || doc.file_name || "Tài liệu"}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <span className={`w-2 h-2 rounded-full ${isProcessed ? 'bg-green-500' : 'bg-yellow-500'}`}></span>
              <span className={`text-xs font-medium ${isProcessed ? 'text-green-600' : 'text-yellow-600'}`}>
                {doc.status || "Đang xử lý"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="space-y-3 mb-6">
        {doc.file_name && doc.file_name !== doc.title && (
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs text-gray-500 font-medium mb-1">Tên file</div>
            <div className="text-sm text-gray-700 truncate">{doc.file_name}</div>
          </div>
        )}
        
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs text-gray-500 font-medium mb-1">Số đoạn</div>
            <div className="text-2xl font-bold text-gray-900">{doc.segments ?? 0}</div>
          </div>
          
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs text-gray-500 font-medium mb-1">Hình ảnh</div>
            <div className="text-2xl font-bold text-gray-900">{doc.images ?? 0}</div>
          </div>
        </div>

        <div className="bg-gray-50 rounded-lg p-3">
          <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
            <Clock className="h-3 w-3" />
            <span className="font-medium">Thời gian</span>
          </div>
          <div className="text-sm text-gray-700">
            <div>Tạo: {doc.created_at || "-"}</div>
            <div>Cập nhật: {doc.updated_at || "-"}</div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={deleting}
          className="flex-1 bg-white flex items-center justify-center gap-2 hover:bg-red-50 hover:text-red-600 hover:border-red-300"
          onClick={handleDelete}
        >
          {deleting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
          <span>Xóa</span>
        </Button>
      </div>
    </div>
  );
}

function KnowledgeContent() {
  const [activeTab, setActiveTab] = useState("documents");
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  useEffect(() => {
    fetchKnowledge();
  }, []);

  const fetchKnowledge = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getDocuments();
      if (res.success) {
        setKnowledgeDocs(res.data || []);
      } else {
        setError(res.message || "Không thể tải tài liệu");
      }
    } catch (err: any) {
      setError(err.message || "Lỗi kết nối đến máy chủ");
    } finally {
      setLoading(false);
    }
  };

  const filteredDocs = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    if (!q) return knowledgeDocs;
    return knowledgeDocs.filter((d) =>
      (d.title || d.file_name || "").toLowerCase().includes(q)
    );
  }, [knowledgeDocs, searchTerm]);

  const onDelete = async (doc: KnowledgeDocument) => {
    if (!confirm(`Bạn có chắc chắn muốn xóa "${doc.title || doc.file_name}"?`)) return;
    try {
      const res = await deleteDocument(doc.id);
      if (res.success) {
        await fetchKnowledge();
      } else {
        setError(res.message || "Không thể xóa tài liệu");
      }
    } catch (err: any) {
      setError(err.message || "Không thể xóa tài liệu");
    }
  };

  const handleUploaded = async (doc: KnowledgeDocument) => {
    await fetchKnowledge();
    // Poll for processing status
    let attempts = 0;
    const poll = async () => {
      attempts += 1;
      if (attempts > 20) return;
      try {
        const docs = await getDocuments();
        const found = (docs.data || []).find((d) => String(d.id) === String(doc.id));
        if (found && (found.status || "").toLowerCase().includes("đã xử lý")) {
          await fetchKnowledge();
          return;
        }
      } catch {}
      setTimeout(poll, 3000);
    };
    setTimeout(poll, 3000);
  };

  const processedDocs = knowledgeDocs.filter(d => 
    (d.status || "").toLowerCase().includes("xử lý")
  ).length;

  return (
    <div className="min-h-screen from-slate-50 to-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black mb-2">
              Cơ sở kiến thức
            </h1>
            <p className="text-gray-600">Quản lý và tổ chức tài liệu kiến thức của bạn</p>
          </div>
          <Button
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
            onClick={() => setUploadOpen(true)}
          >
            <Upload className="mr-2 h-5 w-5" />
            Tải lên tài liệu
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <FileText className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Tổng tài liệu</div>
                <div className="text-3xl font-bold text-gray-900">{knowledgeDocs.length}</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-md">
                <BrainCircuit className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Đã xử lý</div>
                <div className="text-3xl font-bold text-gray-900">{processedDocs}</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-md">
                <File className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Cặp Q&A</div>
                <div className="text-3xl font-bold text-gray-900">—</div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters & Tabs */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
            {/* Tabs */}
            <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg">
              <button
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === "documents"
                    ? "bg-white text-blue-600 shadow-sm"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setActiveTab("documents")}
              >
                Tài liệu
              </button>
              <button
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  activeTab === "qna"
                    ? "bg-white text-blue-600 shadow-sm"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                onClick={() => setActiveTab("qna")}
              >
                Cặp Q&A
              </button>
            </div>

            {/* Search & View Toggle */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <Input
                  placeholder="Tìm kiếm tài liệu..."
                  className="pl-10 border-gray-300 focus:border-blue-500 focus:ring-blue-500"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <div className="flex gap-2">
                <Button
                  size="icon"
                  onClick={() => setViewMode("grid")}
                  className={
                    viewMode === "grid"
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"
                  }
                >
                  <Grid3x3 className="h-4 w-4" />
                </Button>

                <Button
                  size="icon"
                  onClick={() => setViewMode("list")}
                  className={
                    viewMode === "list"
                      ? "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-100"
                  }
                >
                  <List className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 animate-in fade-in duration-300">
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
              Đóng
            </Button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col justify-center items-center py-20">
            <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
            <span className="text-gray-600 font-medium">Đang tải tài liệu...</span>
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredDocs.length === 0 && !error && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
              <FileText className="w-10 h-10 text-gray-400" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {searchTerm ? "Không tìm thấy tài liệu phù hợp" : "Chưa có tài liệu nào"}
            </h3>
            <p className="text-gray-500 mb-6">
              {searchTerm
                ? "Thử điều chỉnh từ khóa tìm kiếm"
                : "Bắt đầu tải lên tài liệu đầu tiên của bạn"}
            </p>
            {!searchTerm && (
              <Button
                className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                onClick={() => setUploadOpen(true)}
              >
                <Plus className="mr-2 h-5 w-5" />
                Tải lên tài liệu
              </Button>
            )}
          </div>
        )}

        {/* Documents Grid/List */}
        {!loading && activeTab === "documents" && filteredDocs.length > 0 && (
          <div className={viewMode === "grid" ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
            {filteredDocs.map((doc, idx) => (
              <DocumentCard
                
                key={String(doc.id) || `doc-${idx}`}
                doc={doc}
                index={idx}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}

        {/* Q&A Tab */}
        {!loading && activeTab === "qna" && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
              <BrainCircuit className="w-10 h-10 text-gray-400" />
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Tính năng đang phát triển
            </h3>
            <p className="text-gray-500">
              Giao diện quản lý Cặp Q&A sẽ sớm được ra mắt
            </p>
          </div>
        )}

        {/* Upload Modal */}
        <UploadDocumentModal
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onUploaded={handleUploaded}
        />
      </div>
    </div>
  );
}

export default function KnowledgePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen from-slate-50 to-slate-50 p-6 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
          <span className="text-gray-600 font-medium">Đang tải...</span>
        </div>
      </div>
    }>
      <KnowledgeContent />
    </Suspense>
  );
}