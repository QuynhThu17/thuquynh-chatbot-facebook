"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Upload, Loader2 } from "lucide-react";
import {
  getCurrentUser,
  getAvatarInfo,
  uploadAvatar,
  updateAvatar
} from "@/lib/api";

export default function SettingsPage() {
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
    let mounted = true;

    (async () => {
      try {
        const u = await getCurrentUser();
        const d = (u as any)?.data || {};

        if (mounted) {
          setName(d.name || "");
          setEmail(d.email || "");
        }
      } catch {}

      try {
        const a = await getAvatarInfo();
        const raw =
          (a as any)?.data?.avatar_url ||
          (a as any)?.data?.url ||
          (a as any)?.avatar_url ||
          (a as any)?.url;

        if (mounted && raw) {
          const finalUrl = normalizeUrl(raw);
          setAvatarUrl(addTs(finalUrl));
        }
      } catch {}
    })();

    return () => {
      mounted = false;
    };
  }, []);

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
      const res = await uploadAvatar(file);

      const raw =
        (res as any)?.data?.avatar_url ||
        (res as any)?.data?.url ||
        (res as any)?.avatar_url ||
        (res as any)?.url;

      if (!raw) {
        setError("API không trả về URL hợp lệ");
        return;
      }

      const finalUrl = normalizeUrl(raw);

      // Preview ngay lập tức
      setPendingUrl(addTs(finalUrl));
    } catch (err: any) {
      setError(err?.message || "Tải ảnh thất bại");
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
      const res = await updateAvatar(clean);

      if (res?.success !== false) {
        // cập nhật avatar ngay, chống cache
        setAvatarUrl(addTs(clean));
        setPendingUrl(undefined);
      }
    } catch (err: any) {
      setError(err?.message || "Cập nhật avatar thất bại");
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
    <div className="space-y-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Cài đặt</h1>
        <p className="text-gray-500">Quản lý cài đặt và avatar</p>
      </div>

      <Card className="bg-white border">
        <CardHeader>
          <CardTitle className="text-black">Thông tin hồ sơ</CardTitle>
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
                className="bg-white text-black flex items-center gap-2"
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

            {error && (
              <div className="col-span-2 text-sm text-red-600">{error}</div>
            )}

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
  );
}
