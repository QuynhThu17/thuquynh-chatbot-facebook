"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Grip,
  List,
  Search,
  Upload,
  FileText,
  BrainCircuit,
  Trash2,
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
  const statusColor = (doc.status || "").toLowerCase().includes("xử lý")
    ? "text-green-700 bg-green-100"
    : "text-yellow-700 bg-yellow-100";
  return (
    <Card className="flex flex-col bg-white text-gray-900 border hover:shadow-sm transition-shadow">
      <CardHeader className="flex-row items-start justify-between">
        <CardTitle className="text-base font-bold">
          {index + 1}. {doc.title || "Tài liệu"}
        </CardTitle>
        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${statusColor}`}>
          {doc.status || "Đang xử lý"}
        </span>
      </CardHeader>
      <CardContent className="flex-grow space-y-2 text-sm text-gray-600">
        {doc.file_name && <p className="text-gray-700">{doc.file_name}</p>}
        <p>
          Số đoạn: <span className="font-semibold text-gray-800">{doc.segments ?? 0}</span> Số hình ảnh: <span className="font-semibold text-gray-800">{doc.images ?? 0}</span>
        </p>
        <p>
          Ngày tạo: {doc.created_at || "-"} Cập nhật: {doc.updated_at || "-"}
        </p>
      </CardContent>
      <div className="flex items-center justify-end p-4 border-t gap-2">
        <Button variant="outline" size="icon" className="text-red-600 hover:bg-red-50 bg-white" onClick={() => onDelete(doc)}>
          <Trash2 className="w-5 h-5" />
        </Button>
      </div>
    </Card>
  );
}

function KnowledgeContent() {
  
  const [activeTab, setActiveTab] = useState("Tài liệu");
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);

  useEffect(() => {
    const run = async () => {
      await fetchKnowledge();
    };
    run();
  }, []);

  const fetchKnowledge = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getDocuments();
      if (res.success) {
        setKnowledgeDocs(res.data || []);
      } else {
        setError(res.message || "Không thể tải tài liệu kiến thức của bạn");
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
    return knowledgeDocs.filter((d) => (d.title || d.file_name || "").toLowerCase().includes(q));
  }, [knowledgeDocs, searchTerm]);

  const onDelete = async (doc: KnowledgeDocument) => {
    if (!confirm("Xóa tài liệu khỏi cơ sở kiến thức của bạn?")) return;
    try {
      const res = await deleteDocument(doc.id);
      if (res.success) await fetchKnowledge();
    } catch {}
  };

  const handleUploaded = async (doc: KnowledgeDocument) => {
    try {
      await fetchKnowledge();
      // Poll processing status and refresh until processed
      let attempts = 0;
      const poll = async () => {
        attempts += 1;
        if (attempts > 20) return; // ~60s if interval 3s
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
    } catch {}
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Cơ sở kiến thức</h1>
        <p className="text-gray-500">Quản lý và tổ chức tài liệu kiến thức của bạn</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white text-gray-900 border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tổng số tài liệu</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{knowledgeDocs.length}</div>
          </CardContent>
        </Card>
        <Card className="bg-white text-gray-900 border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tổng số cặp Q&A</CardTitle>
            <BrainCircuit className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">—</div>
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center border-b">
          <button
            className={`px-4 py-2 text-sm font-medium ${activeTab === "Tài liệu" ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-500"}`}
            onClick={() => setActiveTab("Tài liệu")}
          >
            Tài liệu
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium ${activeTab === "Cặp Q&A" ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-500"}`}
            onClick={() => setActiveTab("Cặp Q&A")}
          >
            Cặp Q&A
          </button>
        </div>
      </div>

      <div className="flex justify-between items-center mb-6">
        <div className="relative w-1/3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input placeholder="Tìm kiếm tài liệu..." className="pl-10 bg-white text-gray-900" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="icon" className="bg-white">
            <Grip className="w-5 h-5" />
          </Button>
          <Button variant="ghost" size="icon" className="bg-white">
            <List className="w-5 h-5" />
          </Button>
          <Button onClick={() => setUploadOpen(true)} className="bg-blue-600 hover:bg-blue-700 text-white">
            <Upload className="w-5 h-5 mr-2" />
            Tải lên tài liệu
          </Button>
        </div>
      </div>

      

      {activeTab === "Tài liệu" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading && (
            <div className="col-span-full text-center text-gray-500 py-12">Đang tải...</div>
          )}
          {!loading && filteredDocs.map((doc, idx) => (
            <DocumentCard key={String(doc.id) || `doc-${idx}`} doc={doc} index={idx} onDelete={onDelete} />
          ))}
          {!loading && filteredDocs.length === 0 && (
            <div className="col-span-full text-center text-gray-500 py-12">Không có tài liệu nào</div>
          )}
        </div>
      )}
      {activeTab === "Cặp Q&A" && (
        <div className="text-center text-gray-500 py-12">
          <p>Giao diện cho Cặp Q&A sẽ được xây dựng ở đây.</p>
        </div>
      )}

      <UploadDocumentModal open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={handleUploaded} />
    </div>
  );
}

export default function KnowledgePage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-600">Đang tải...</div>}>
      <KnowledgeContent />
    </Suspense>
  );
}