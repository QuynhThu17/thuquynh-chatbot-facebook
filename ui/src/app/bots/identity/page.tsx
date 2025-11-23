"use client";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AppWindow,
  Copy,
  Edit,
  Grip,
  List,
  MessageSquare,
  Eye,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { type Identity, getIdentities, copyIdentity } from "@/lib/api";
import { IdentityDetailsModal } from "@/components/identity-details-modal";

function IdentityCard({ identity, onCopy, onView }: { identity: Identity; onCopy: (id: Identity["id"]) => Promise<void>; onView: (i: Identity) => void }) {
  return (
    <Card className="flex flex-col bg-white text-black border border-gray-200">
      <CardHeader>
        <CardTitle className="text-base font-bold text-gray-900">
          {identity.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-grow">
        <p className="text-sm text-gray-700 line-clamp-2 break-words">
          {identity.description}
        </p>
        <div className="flex items-center text-sm text-gray-600 mt-4">
          <MessageSquare className="w-4 h-4 mr-2" />
          {identity.examples} ví dụ
        </div>
      </CardContent>
      <div className="flex items-center justify-end p-4 border-t">
        <Button
          variant="outline"
          size="sm"
          className="flex items-center gap-2 bg-white"
          onClick={() => onView(identity)}
        >
          <Eye className="h-4 w-4" />
          Xem
        </Button>
        <Button variant="ghost" size="icon">
          <AppWindow className="w-5 h-5" />
        </Button>
        <Button variant="ghost" size="icon">
          <Edit className="w-5 h-5" />
        </Button>
        <Button variant="ghost" size="icon" onClick={() => onCopy(identity.id)} aria-label="Sao chép danh tính">
          <Copy className="w-5 h-5" />
        </Button>
        <Button variant="ghost" size="icon" className="text-red-600">
          <Trash2 className="w-5 h-5" />
        </Button>
      </div>
    </Card>
  );
}

export default function IdentityPage() {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selected, setSelected] = useState<Identity | null>(null);
  const [open, setOpen] = useState<boolean>(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getIdentities();
        if (res.success) {
          setIdentities(res.data || []);
        } else {
          setError(res.message || "Không thể tải danh sách danh tính");
        }
      } catch (err: any) {
        setError(err.message || "Lỗi kết nối máy chủ");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return identities;
    return identities.filter((i) =>
      `${i.title} ${i.description || ""}`.toLowerCase().includes(term)
    );
  }, [identities, searchTerm]);

  const totalExamples = useMemo(
    () => identities.reduce((sum, i) => sum + (i.examples || 0), 0),
    [identities]
  );

  const onCopy = async (id: Identity["id"]) => {
    try {
      const res = await copyIdentity(id);
      if (res?.success && res?.data) {
        // Thêm bản sao vào danh sách hiện tại
        setIdentities((prev) => [res.data, ...prev]);
      }
    } catch (err) {
      console.error("Copy identity failed", err);
    }
  };

  const onView = (i: Identity) => {
    setSelected(i);
    setOpen(true);
  };

  return (
    <div className="p-8">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card className="bg-white text-black border border-gray-200">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">
              Tổng số Danh tính
            </CardTitle>
            <AppWindow className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">{identities.length}</div>
          </CardContent>
        </Card>
        <Card className="bg-white text-black border border-gray-200">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">
              Tổng số Ví dụ
            </CardTitle>
            <MessageSquare className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-900">{totalExamples}</div>
          </CardContent>
        </Card>
      </div>

      <div className="flex justify-between items-center mb-6">
        <div className="relative w-1/3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            placeholder="Tìm kiếm danh tính..."
            className="pl-10"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="icon">
            <Grip className="w-5 h-5" />
          </Button>
          <Button variant="ghost" size="icon">
            <List className="w-5 h-5" />
          </Button>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white">
            <Plus className="w-5 h-5 mr-2" />
            Tạo Danh tính
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-6 text-sm text-red-600">{error}</div>
      )}

      {loading ? (
        <div className="text-gray-600">Đang tải...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((identity, index) => (
            <IdentityCard 
              key={identity.id || `identity-${index}`} 
              identity={identity} 
              onCopy={onCopy}
              onView={onView}
            />
          ))}
        </div>
      )}

      <IdentityDetailsModal identity={selected} open={open} onClose={() => setOpen(false)} />
    </div>
  );
}