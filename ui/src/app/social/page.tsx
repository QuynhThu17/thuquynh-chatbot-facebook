"use client";
import Image from 'next/image';
import { useState, useEffect } from 'react';
import { Share2, Zap, UserPlus, Settings, CheckCircle, Loader2, X, ArrowLeft } from 'lucide-react';
import { connectSocial, getSocialAccounts, type SocialAccount } from '@/lib/api';

const SocialPage = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [step1Done, setStep1Done] = useState(false);
  const [step2Done, setStep2Done] = useState(false);
  const [step3Done, setStep3Done] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [showAccountsView, setShowAccountsView] = useState(false);

  const SOCIAL_ID = "s_facebook";

  async function startConnect() {
    setIsConnecting(true);
    setErrorMsg(null);
    setStep1Done(false);
    setStep2Done(false);
    setStep3Done(false);
    try {
      const res = await connectSocial(SOCIAL_ID);
      const authUrl = (res as any)?.data?.auth_url;
      setStep1Done(true);
      if (authUrl && typeof window !== "undefined") {
        window.open(authUrl, "_blank", "noopener,noreferrer");
      }
      setStep2Done(true);
      const accRes = await getSocialAccounts(SOCIAL_ID);
      setAccounts(accRes.data || []);
      setStep3Done(true);
      setIsModalOpen(false);
      setShowAccountsView(true);
    } catch (err: any) {
      const msg = err?.message || "Không thể kết nối";
      setErrorMsg(msg);
      // Nếu 403 (không có quyền / chưa đăng nhập), vẫn cho phép vào danh sách tài khoản
      // và thử tải danh sách hiện có để tránh trạng thái rỗng giả.
      if ((err?.status ?? String(msg)).toString().includes("403")) {
        setShowAccountsView(true);
        await loadAccounts();
      }
    } finally {
      setIsConnecting(false);
    }
  }

  async function loadAccounts() {
    try {
      const accRes = await getSocialAccounts(SOCIAL_ID);
      setAccounts(accRes.data || []);
    } catch (err) {
      // Hiển thị thông báo lỗi khi không thể tải danh sách (ví dụ 403)
      const msg = (err as any)?.message || "Không thể tải danh sách tài khoản";
      setErrorMsg(msg);
    }
  }

  function openAccountsView() {
    setShowAccountsView(true);
  }

  function openModal() {
    setIsModalOpen(true);
  }

  function closeModal() {
    if (!isConnecting) setIsModalOpen(false);
  }

  useEffect(() => {
    if (showAccountsView && accounts.length === 0) {
      loadAccounts();
    }
  }, [showAccountsView]);

  // Tự động tải danh sách tài khoản khi vào trang để hiển thị luôn nếu đã có kết nối trước đó
  useEffect(() => {
    loadAccounts().catch(() => {});
  }, []);

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <h1 className="text-3xl font-bold">Kết nối mạng xã hội</h1>
      <p className="text-gray-500 mt-2">
        Quản lý các nền tảng mạng xã hội và tài khoản đã kết nối
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
        <div className="bg-white p-6 rounded-lg shadow-sm flex items-center">
          <div className="bg-blue-100 p-3 rounded-full">
            <Share2 className="w-6 h-6 text-blue-500" />
          </div>
          <div className="ml-4">
            <p className="text-gray-500">Tổng số nền tảng</p>
            <p className="text-2xl font-bold">1</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg shadow-sm flex items-center">
          <div className="bg-green-100 p-3 rounded-full">
            <Zap className="w-6 h-6 text-green-500" />
          </div>
          <div className="ml-4">
            <p className="text-gray-500">Nền tảng đang hoạt động</p>
            <p className="text-2xl font-bold">1</p>
          </div>
        </div>
      </div>

      {!showAccountsView && (
        <div className="mt-10 bg-white p-8 rounded-lg shadow-sm">
          <h2 className="text-xl font-bold">Nền tảng khả dụng</h2>
          <p className="text-gray-500 mt-1">
            Kết nối các nền tảng mạng xã hội để bắt đầu tương tác với khách hàng
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
            <div className="border rounded-lg p-6 flex flex-col items-center text-center">
              <Image src="/facebook.svg" alt="Facebook" width={56} height={56} />
              <p className="font-bold mt-4">Facebook</p>
              <div className="flex space-x-2 mt-4">
                <button onClick={openModal} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center">
                  <UserPlus className="w-4 h-4 mr-2" />
                  Kết nối
                </button>
                <button onClick={() => { openAccountsView(); loadAccounts(); }} className="border px-4 py-2 rounded-lg text-sm font-semibold flex items-center">
                  <Settings className="w-4 h-4 mr-2" />
                  Tài khoản
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showAccountsView && (
        <div className="mt-10">
          <button onClick={() => setShowAccountsView(false)} className="mb-4 flex items-center text-sm font-semibold">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Tất cả mạng xã hội
          </button>
          <div className="bg-white p-6 rounded-lg shadow-sm">
            <h3 className="text-lg font-bold">Tài khoản đã kết nối</h3>
            <div className="mt-4 space-y-3">
              {accounts.map((a) => (
                <div key={String(a.id)} className="flex items-center justify-between border rounded-lg p-4">
                  <div className="flex items-center">
                    {a.avatar_url ? (
                      <Image src={a.avatar_url} alt={a.name} width={40} height={40} className="rounded-full" />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gray-200" />
                    )}
                    <div className="ml-4">
                      <p className="font-medium">{a.name}</p>
                      <p className="text-xs text-gray-500">Đã kết nối</p>
                    </div>
                  </div>
                  <div className="flex space-x-2">
                    <button onClick={() => {
                      if (typeof window !== "undefined") {
                        window.open(`/social/facebook/pages`, "_blank");
                      }
                    }} className="border px-3 py-1 rounded">Trang</button>
                    <button onClick={loadAccounts} className="border px-3 py-1 rounded">Làm mới</button>
                  </div>
                </div>
              ))}
              {accounts.length === 0 && (
                <div className="text-sm text-gray-600">Chưa có tài khoản được đồng bộ.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={closeModal} />
          <div className="relative bg-white w-[520px] rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <Image src="/facebook.svg" alt="Facebook" width={24} height={24} />
                <p className="ml-2 font-semibold">Kết nối Facebook</p>
              </div>
              <button onClick={closeModal} className="p-1 rounded hover:bg-gray-100">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-gray-600 mt-2">Cho phép MekongAI truy cập tài khoản Facebook của bạn</p>

            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between bg-green-50 p-3 rounded-lg">
                <div>
                  <p className="font-medium">Xác thực ứng dụng</p>
                  <p className="text-sm text-gray-600">Đang chuyển hướng đến trang xác thực</p>
                </div>
                {step1Done ? <CheckCircle className="w-5 h-5 text-green-600" /> : <Loader2 className="w-5 h-5 animate-spin text-green-600" />}
              </div>
              <div className="flex items-center justify-between bg-green-50 p-3 rounded-lg">
                <div>
                  <p className="font-medium">Cấp quyền truy cập</p>
                  <p className="text-sm text-gray-600">Chấp nhận các quyền cần thiết cho tích hợp</p>
                </div>
                {step2Done ? <CheckCircle className="w-5 h-5 text-green-600" /> : <Loader2 className="w-5 h-5 animate-spin text-green-600" />}
              </div>
              <div className="flex items-center justify-between bg-green-50 p-3 rounded-lg">
                <div>
                  <p className="font-medium">Đồng bộ dữ liệu</p>
                  <p className="text-sm text-gray-600">Đang nhập thông tin và cài đặt tài khoản</p>
                </div>
                {step3Done ? <CheckCircle className="w-5 h-5 text-green-600" /> : <Loader2 className="w-5 h-5 animate-spin text-green-600" />}
              </div>
            </div>

            <div className="mt-4">
              <p className="text-sm font-medium">Quyền yêu cầu</p>
              <ul className="mt-2 text-sm text-gray-700 list-disc ml-5">
                <li>Quản lý bài đăng</li>
                <li>Đọc tương tác</li>
                <li>Nhắn tin</li>
              </ul>
            </div>

            {errorMsg && <p className="mt-3 text-sm text-red-600">{errorMsg}</p>}

            <div className="mt-6 flex justify-between">
              <button onClick={closeModal} disabled={isConnecting} className="px-4 py-2 rounded-lg border">Hủy</button>
              <button onClick={startConnect} disabled={isConnecting} className="px-4 py-2 rounded-lg bg-blue-600 text-white flex items-center">
                {isConnecting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                Bắt đầu kết nối
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SocialPage;