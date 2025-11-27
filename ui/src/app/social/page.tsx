"use client";

import Image from 'next/image';
import { useState, useEffect } from 'react';
import { 
  Share2, 
  Zap, 
  UserPlus, 
  Settings, 
  CheckCircle, 
  Loader2, 
  X, 
  ArrowLeft,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Plus
} from 'lucide-react';
import { connectSocial, getSocialAccounts, type SocialAccount } from '@/lib/api';
import { SocialPagesModal } from '@/components/social-pages-modal';
import { Button } from '@/components/ui/button';

const SocialPage = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [step1Done, setStep1Done] = useState(false);
  const [step2Done, setStep2Done] = useState(false);
  const [step3Done, setStep3Done] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [showAccountsView, setShowAccountsView] = useState(false);
  const [pagesOpen, setPagesOpen] = useState(false);
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      setLoading(true);
      const accRes = await getSocialAccounts(SOCIAL_ID);
      setAccounts(accRes.data || []);
      setErrorMsg(null);
    } catch (err) {
      const msg = (err as any)?.message || "Không thể tải danh sách tài khoản";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
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

  useEffect(() => {
    loadAccounts().catch(() => {});
  }, []);

  const activePlatforms = accounts.length > 0 ? 1 : 0;

  return (
    <div className="min-h-screen from-slate-50 to-slate-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4 mb-8">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-black mb-2">
              Kết nối mạng xã hội
            </h1>
            <p className="text-gray-600">Quản lý các nền tảng mạng xã hội và tài khoản đã kết nối</p>
          </div>
          {showAccountsView && (
            <Button
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
              onClick={openModal}
            >
              <Plus className="mr-2 h-5 w-5" />
              Kết nối mới
            </Button>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                <Share2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Tổng số nền tảng</div>
                <div className="text-3xl font-bold text-gray-900">1</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center shadow-md">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Đang hoạt động</div>
                <div className="text-3xl font-bold text-gray-900">{activePlatforms}</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center shadow-md">
                <UserPlus className="w-6 h-6 text-white" />
              </div>
              <div>
                <div className="text-sm text-gray-500 font-medium">Tài khoản</div>
                <div className="text-3xl font-bold text-gray-900">{accounts.length}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {errorMsg && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3 animate-in fade-in duration-300">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-red-700 font-medium">{errorMsg}</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="flex-shrink-0"
              onClick={() => setErrorMsg(null)}
            >
              Đóng
            </Button>
          </div>
        )}

        {/* Available Platforms View */}
        {!showAccountsView && (
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Nền tảng khả dụng</h2>
              <p className="text-gray-600 mt-1">
                Kết nối các nền tảng mạng xã hội để bắt đầu tương tác với khách hàng
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-all duration-200 hover:border-blue-300">
                <div className="flex flex-col items-center text-center">
                  <div className="w-16 h-16 rounded-lg bg-blue-50 flex items-center justify-center mb-4">
                    <Image src="/facebook.svg" alt="Facebook" width={40} height={40} />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">Facebook</h3>
                  <p className="text-sm text-gray-500 mb-4">
                    Kết nối với Facebook để quản lý trang và tin nhắn
                  </p>

                  <div className="flex flex-col sm:flex-row gap-2 w-full">
                    <Button
                      onClick={openModal}
                      className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                    >
                      <UserPlus className="w-4 h-4 mr-2" />
                      Kết nối
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => { openAccountsView(); loadAccounts(); }}
                      className="flex-1 bg-white hover:bg-gray-50"
                    >
                      <Settings className="w-4 h-4 mr-2" />
                      Tài khoản
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Connected Accounts View */}
        {showAccountsView && (
          <div>
            <Button
              variant="outline"
              onClick={() => setShowAccountsView(false)}
              className="mb-6 bg-white hover:bg-gray-50"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Tất cả mạng xã hội
            </Button>

            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-2xl font-bold text-gray-900">Tài khoản đã kết nối</h3>
                  <p className="text-gray-600 mt-1">Quản lý các tài khoản Facebook đã liên kết</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadAccounts}
                  disabled={loading}
                  className="bg-white hover:bg-gray-50"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4 mr-2" />
                  )}
                  Làm mới
                </Button>
              </div>

              {/* Loading State */}
              {loading && accounts.length === 0 && (
                <div className="flex flex-col justify-center items-center py-12">
                  <Loader2 className="h-12 w-12 animate-spin text-blue-500 mb-4" />
                  <span className="text-gray-600 font-medium">Đang tải tài khoản...</span>
                </div>
              )}

              {/* Accounts List */}
              {!loading && accounts.length > 0 && (
                <div className="space-y-4">
                  {accounts.map((account) => (
                    <div
                      key={String(account.id)}
                      className="flex items-center justify-between border border-gray-200 rounded-xl p-4 hover:border-blue-300 hover:shadow-md transition-all duration-200"
                    >
                      <div className="flex items-center gap-4">
                        {account.avatar_url ? (
                          <div className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-gray-200">
                            <Image 
                              src={account.avatar_url} 
                              alt={account.name} 
                              width={48} 
                              height={48}
                              className="object-cover"
                            />
                          </div>
                        ) : (
                          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-md">
                            {account.name.charAt(0).toUpperCase()}
                          </div>
                        )}
                        <div>
                          <h4 className="font-semibold text-gray-900">{account.name}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            <span className="text-xs font-medium text-green-600">Đã kết nối</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setActiveAccountId(String(account.id));
                            setPagesOpen(true);
                          }}
                          className="bg-white hover:bg-blue-50 hover:text-blue-600 hover:border-blue-300"
                        >
                          <ExternalLink className="w-4 h-4 mr-2" />
                          Trang
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={loadAccounts}
                          className="bg-white hover:bg-gray-50"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Empty State */}
              {!loading && accounts.length === 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
                  <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
                    <UserPlus className="w-10 h-10 text-gray-400" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    Chưa có tài khoản nào
                  </h3>
                  <p className="text-gray-500 mb-6">
                    Kết nối tài khoản Facebook đầu tiên để bắt đầu
                  </p>
                  <Button
                    className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                    onClick={openModal}
                  >
                    <Plus className="mr-2 h-5 w-5" />
                    Kết nối tài khoản
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Connection Modal */}
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/40" onClick={closeModal} />
            <div className="relative bg-white w-full max-w-xl rounded-xl shadow-2xl">
              {/* Modal Header */}
              <div className="flex items-center justify-between p-6 border-b border-gray-200">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                    <Image src="/facebook.svg" alt="Facebook" width={24} height={24} />
                  </div>
                  <h3 className="text-xl font-bold text-gray-900">Kết nối Facebook</h3>
                </div>
                <button
                  onClick={closeModal}
                  disabled={isConnecting}
                  className="p-2 rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-50"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              {/* Modal Content */}
              <div className="p-6">
                <p className="text-gray-600 mb-6">
                  Cho phép HueAI truy cập tài khoản Facebook của bạn để quản lý trang và tin nhắn
                </p>

                {/* Connection Steps */}
                <div className="space-y-3 mb-6">
                  <div className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all ${
                    step1Done 
                      ? 'bg-green-50 border-green-200' 
                      : 'bg-blue-50 border-blue-200'
                  }`}>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900">1. Xác thực ứng dụng</p>
                      <p className="text-sm text-gray-600 mt-1">
                        Đang chuyển hướng đến trang xác thực Facebook
                      </p>
                    </div>
                    {step1Done ? (
                      <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0" />
                    ) : isConnecting ? (
                      <Loader2 className="w-6 h-6 animate-spin text-blue-600 flex-shrink-0" />
                    ) : (
                      <div className="w-6 h-6 rounded-full border-2 border-gray-300 flex-shrink-0" />
                    )}
                  </div>

                  <div className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all ${
                    step2Done 
                      ? 'bg-green-50 border-green-200' 
                      : step1Done 
                      ? 'bg-blue-50 border-blue-200' 
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900">2. Cấp quyền truy cập</p>
                      <p className="text-sm text-gray-600 mt-1">
                        Chấp nhận các quyền cần thiết cho tích hợp
                      </p>
                    </div>
                    {step2Done ? (
                      <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0" />
                    ) : step1Done && isConnecting ? (
                      <Loader2 className="w-6 h-6 animate-spin text-blue-600 flex-shrink-0" />
                    ) : (
                      <div className="w-6 h-6 rounded-full border-2 border-gray-300 flex-shrink-0" />
                    )}
                  </div>

                  <div className={`flex items-start gap-3 p-4 rounded-lg border-2 transition-all ${
                    step3Done 
                      ? 'bg-green-50 border-green-200' 
                      : step2Done 
                      ? 'bg-blue-50 border-blue-200' 
                      : 'bg-gray-50 border-gray-200'
                  }`}>
                    <div className="flex-1">
                      <p className="font-semibold text-gray-900">3. Đồng bộ dữ liệu</p>
                      <p className="text-sm text-gray-600 mt-1">
                        Đang nhập thông tin và cài đặt tài khoản
                      </p>
                    </div>
                    {step3Done ? (
                      <CheckCircle className="w-6 h-6 text-green-600 flex-shrink-0" />
                    ) : step2Done && isConnecting ? (
                      <Loader2 className="w-6 h-6 animate-spin text-blue-600 flex-shrink-0" />
                    ) : (
                      <div className="w-6 h-6 rounded-full border-2 border-gray-300 flex-shrink-0" />
                    )}
                  </div>
                </div>

                {/* Permissions */}
                <div className="bg-gray-50 rounded-lg p-4 mb-4">
                  <p className="text-sm font-semibold text-gray-900 mb-2">Quyền yêu cầu:</p>
                  <ul className="space-y-1 text-sm text-gray-700">
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      Quản lý bài đăng và trang
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      Đọc tin nhắn và tương tác
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      Gửi và nhận tin nhắn
                    </li>
                  </ul>
                </div>

                {/* Error Message */}
                {errorMsg && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-start gap-2">
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-700">{errorMsg}</p>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="flex justify-between gap-3 p-6 border-t border-gray-200">
                <Button
                  variant="outline"
                  onClick={closeModal}
                  disabled={isConnecting}
                  className="bg-white hover:bg-gray-50"
                >
                  Hủy
                </Button>
                <Button
                  onClick={startConnect}
                  disabled={isConnecting}
                  className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white"
                >
                  {isConnecting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Đang kết nối...
                    </>
                  ) : (
                    <>
                      <UserPlus className="w-4 h-4 mr-2" />
                      Bắt đầu kết nối
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Social Pages Modal */}
        {pagesOpen && activeAccountId && (
          <SocialPagesModal
            open={pagesOpen}
            onClose={() => setPagesOpen(false)}
            socialId={SOCIAL_ID}
            accountId={activeAccountId}
          />
        )}
      </div>
    </div>
  );
};

export default SocialPage;