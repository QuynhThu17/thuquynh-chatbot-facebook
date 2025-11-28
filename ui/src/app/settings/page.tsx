"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Upload, Loader2, AlertCircle } from "lucide-react";
import { useCurrentUserQuery, useAvatarInfoQuery, useUploadAvatarMutation, useUpdateAvatarMutation } from "@/lib/queries";

export default function SettingsPage() {
  const userQuery = useCurrentUserQuery();
  const avatarQuery = useAvatarInfoQuery();
  const uploadMutation = useUploadAvatarMutation();
  const updateMutation = useUpdateAvatarMutation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const [avatarUrl, setAvatarUrl] = useState<string | undefined>(undefined);
  const [pendingUrl, setPendingUrl] = useState<string | undefined>(undefined);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Hàm chuẩn hóa URL để chắc chắn là tuyệt đối
  const normalizeUrl = (url: string) => {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    return process.env.NEXT_PUBLIC_API_BASE_URL + url;
  };

  const addTs = (url: string) => url.split("?")[0] + "?t=" + Date.now();

  // ===================================================
  // LOAD USER + CURRENT AVATAR
  // ===================================================

  useEffect(() => {
    const du = (userQuery.data as any) || {};
    setName(du?.name || "");
    setEmail(du?.email || "");
    const ai = (avatarQuery.data as any) || {};
    const raw = ai?.avatar_url || ai?.url;
    if (raw) {
      const finalUrl = normalizeUrl(raw);
      setAvatarUrl(addTs(finalUrl));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userQuery.data, avatarQuery.data]);

  // ===================================================
  // FORM HELPERS
  // ===================================================

  const canSave = useMemo(
    () => !!pendingUrl && !loading && !saving,
    [pendingUrl, loading, saving]
  );

  const onChooseFile = () => fileInputRef.current?.click();

  // ===================================================
  // HANDLE FILE UPLOAD
  // ===================================================

  const onFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!/^(image\/jpeg|image\/png|image\/gif)$/i.test(file.type))
      return setError("Chỉ hỗ trợ JPG, PNG hoặc GIF");

    if (file.size > 2 * 1024 * 1024)
      return setError("Dung lượng tối đa 2MB");

    setLoading(true);
    setError(null);

    try {
      const res = await uploadMutation.mutateAsync(file);
      const ur = res as any;
      const raw = ur?.avatar_url || ur?.url;

      if (!raw) {
        setError("API không trả về URL hợp lệ");
        return;
      }

      const finalUrl = normalizeUrl(raw);

      // Preview ngay lập tức
      setPendingUrl(addTs(finalUrl));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Tải ảnh thất bại";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const onCancel = () => {
    setPendingUrl(undefined);
    setError(null);
  };

  // ===================================================
  // SAVE AVATAR
  // ===================================================

  const onSave = async () => {
    if (!pendingUrl) return;

    setSaving(true);
    setError(null);

    try {
      const clean = pendingUrl.split("?")[0];
      const res = await updateMutation.mutateAsync(clean);
      if (res) {
        setAvatarUrl(addTs(clean));
        setPendingUrl(undefined);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Cập nhật avatar thất bại";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  // ưu tiên preview
  const preview = pendingUrl || avatarUrl;

  // ===================================================
  // UI
  // ===================================================

  return (
    <div className="min-h-screen from-slate-50 to-slate-50 p-6">
      <div>
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black mb-2">Cài đặt</h1>
            <p className="text-gray-600">Quản lý cài đặt tài khoản và ảnh đại diện</p>
          </div>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 animate-in fade-in duration-300">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-700 font-medium">{error}</p>
            </div>
            <Button 
              variant="outline" 
              size="sm" 
              className="flex-shrink-0 bg-white text-gray-700 border border-gray-300 hover:bg-gray-10"
              onClick={() => setError(null)}
            >
              Đóng
            </Button>
          </div>
        )}

        <Card className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <CardHeader>
            <CardTitle className="text-gray-700">Thông tin hồ sơ</CardTitle>
          </CardHeader>

          <CardContent>
            {/* Avatar Section */}
          <div className="flex gap-4 items-start mb-6">
            <div className="w-20 h-20 rounded-lg overflow-hidden border flex items-center justify-center bg-gray-100">
              {preview ? (
                <img
                  src={preview}
                  alt="avatar"
                  className="w-20 h-20 object-cover"
                />
              ) : (
                <div className="w-10 h-10 bg-gray-200 rounded-full" />
              )}
            </div>

            <div>
              <Button
                variant="outline"
                size="sm"
                className="bg-white text-black flex items-center gap-2 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-300"
                disabled={loading || saving}
                onClick={onChooseFile}
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                {loading ? "Đang tải..." : "Thay đổi"}
              </Button>

              <div className="text-xs text-gray-600 mt-2">
                JPG, PNG, GIF — tối đa 2MB
              </div>

              <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                hidden
                onChange={onFileSelected}
              />
            </div>
          </div>

          {/* Form */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <div className="text-black mb-1">Họ và tên *</div>
              <Input
                className="text-black"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div>
              <div className="text-black mb-1">Email *</div>
              <Input className="text-black" value={email} disabled />
            </div>
            {(loading || saving) && (
              <div className="col-span-2 flex items-center gap-2 text-sm text-gray-600">
                <Loader2 className="w-4 h-4 animate-spin" />
                {loading ? "Đang tải ảnh..." : "Đang lưu..."}
              </div>
            )}
          </div>
        </CardContent>
        </Card>
      </div>
    </div>
  );
}
