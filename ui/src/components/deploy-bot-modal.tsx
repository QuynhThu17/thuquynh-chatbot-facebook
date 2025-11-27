"use client";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  connectSocial,
  getSocials,
  getSocialAccounts,
  getSocialPages,
  connectBotToSocial,
  type Bot,
  type SocialAccount,
  type SocialPlatform,
  type SocialPage,
} from "@/lib/api";
import { Rocket, Globe, UserPlus, Loader2, X, AlertCircle } from "lucide-react";

type Step = 0 | 1 | 2 | 3 | 4 | 5;

export function DeployBotModal({ bot, open, onClose }: { bot: Bot | null; open: boolean; onClose: () => void }) {
  const [step, setStep] = useState<Step>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [platforms, setPlatforms] = useState<SocialPlatform[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<string | number | null>(null);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string | number | null>(null);
  const [pages, setPages] = useState<SocialPage[]>([]);
  const [selectedPage, setSelectedPage] = useState<string | number | null>(null);
  const [selectedPlatformName, setSelectedPlatformName] = useState<string>("");
  const [selectedAccountName, setSelectedAccountName] = useState<string>("");
  const [selectedPageName, setSelectedPageName] = useState<string>("");
  const [testMessages, setTestMessages] = useState<{ from: "bot" | "user"; text: string }[]>([]);
  const [testInput, setTestInput] = useState("");
  const [deploying, setDeploying] = useState(false);
  const [deployed, setDeployed] = useState(false);
  const [botId, setBotId] = useState<string>("");

  useEffect(() => {
    if (!open) return;
    setStep(0);
    setError(null);
    setSelectedPlatform(null);
    setSelectedAccount(null);
    setSelectedPage(null);
    setSelectedPlatformName("");
    setSelectedAccountName("");
    setSelectedPageName("");
    setTestMessages([]);
    setDeployed(false);
    setBotId(bot?.id ? String(bot.id) : "");
    (async () => {
      try {
        setLoading(true);
        const res = await getSocials();
        setPlatforms(res.data || []);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Không thể tải dữ liệu mạng xã hội";
        setError(msg);
      } finally {
        setLoading(false);
      }
    })();
  }, [open]);

  useEffect(() => {
    setBotId(bot?.id ? String(bot.id) : "");
  }, [bot]);

  const canNext = useMemo(() => {
    if (step === 0) return true;
    if (step === 1) return !!selectedPlatform;
    if (step === 2) return !!selectedAccount;
    if (step === 3) return !!selectedPage;
    if (step === 4) return true;
    if (step === 5) return false;
    return false;
  }, [step, selectedPlatform, selectedAccount, selectedPage, botId]);

  const onNext = async () => {
    if (step === 0) {
      setStep(1);
      return;
    }
    if (step === 1 && selectedPlatform) {
      try {
        setLoading(true);
        const accRes = await getSocialAccounts(selectedPlatform);
        setAccounts(accRes.data || []);
        setStep(2);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Không thể tải tài khoản";
        setError(msg);
      } finally {
        setLoading(false);
      }
      return;
    }
    if (step === 2 && selectedPlatform && selectedAccount) {
      try {
        setLoading(true);
        const pageRes = await getSocialPages(selectedPlatform, selectedAccount);
        setPages(pageRes.data || []);
        setStep(3);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Không thể tải danh sách trang";
        setError(msg);
      } finally {
        setLoading(false);
      }
      return;
    }
    if (step === 3) {
      setStep(4);
      return;
    }
    if (step === 4) {
      const idToUse = String((bot?.id ?? botId) || "");
      const hasSelections = idToUse.trim() !== "" && String(selectedPlatform || "").trim() !== "" && String(selectedAccount || "").trim() !== "" && String(selectedPage || "").trim() !== "";
      if (hasSelections) {
        try {
          setDeploying(true);
          setError(null);
          const res = await connectBotToSocial(idToUse, {
            social_id: String(selectedPlatform),
            social_page_id: String(selectedPage),
          });
          setDeployed(Boolean(res?.success ?? true));
          setStep(5);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Không thể triển khai bot";
          setError(msg);
        } finally {
          setDeploying(false);
        }
      } else {
        setError("Vui lòng chọn đầy đủ nền tảng, tài khoản và trang");
      }
      return;
    }
  };

  const onBack = () => {
    if (step === 0) return;
    setError(null);
    setStep((prev) => (prev > 0 ? ((prev - 1) as Step) : prev));
  };

  const onConnect = async () => {
    if (!selectedPlatform) return;
    try {
      setLoading(true);
      const res = await connectSocial(selectedPlatform);
      const authData = (res as { data?: { auth_url?: string } }).data;
      const authUrl = authData?.auth_url;
      if (authUrl && typeof window !== "undefined") {
        window.open(authUrl, "_blank", "noopener,noreferrer");
      }
      const accRes = await getSocialAccounts(selectedPlatform);
      setAccounts(accRes.data || []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Không thể kết nối mạng xã hội";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const sendTest = () => {
    const text = testInput.trim();
    if (!text) return;
    setTestMessages((msgs) => [...msgs, { from: "user", text }, { from: "bot", text: "Xin chào! Tôi có thể giúp gì?" }]);
    setTestInput("");
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={() => (!deploying ? onClose() : null)} />
      <div className="absolute inset-0 flex items-start justify-center overflow-y-auto p-6">
        <div className="relative w-full max-w-3xl bg-white rounded-xl border border-gray-200 shadow-xl" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between p-6 border-b">
            <div className="flex items-center gap-2">
              <Rocket className="w-5 h-5 text-blue-600" />
              <div>
                <div className="text-lg font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">Kiểm tra & Triển khai Bot</div>
                <div className="text-sm text-gray-600">Cấu hình và triển khai bot lên các nền tảng mạng xã hội</div>
              </div>
            </div>
            <Button variant="outline" size="icon" className="bg-white" onClick={onClose} disabled={deploying}>
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="px-6 pt-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${step >= 0 ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}>Chọn Kết Nối</span>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${step >= 1 ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}>Nền tảng</span>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${step >= 2 ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}>Tài khoản</span>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${step >= 3 ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}>Trang</span>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${step >= 4 ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}>Kiểm thử</span>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${step >= 5 ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600"}`}>Triển khai</span>
            </div>
          </div>

          <div className="p-6 space-y-4">
            {error && (
              <div className="mb-2 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-red-700 text-sm font-medium">{error}</p>
                </div>
                <Button variant="outline" size="sm" className="flex-shrink-0 bg-white text-gray-700 border border-gray-300 hover:bg-gray-10" onClick={() => setError(null)}>Đóng</Button>
              </div>
            )}

            {step === 0 && (
              <div>
                <div className="text-sm text-gray-600 mb-2">Chọn một kết nối hiện có hoặc tạo mới</div>
                <div className="space-y-3">
                  {(platforms || []).length === 0 && (
                    <div className="text-sm text-gray-600">Chưa có kết nối nào</div>
                  )}
                  {(platforms || []).map((p) => (
                    <div key={String(p.id)} className="flex items-center justify-between border border-gray-200 rounded-lg p-4 bg-white">
                      <div className="flex items-center gap-3">
                        <Globe className="w-5 h-5 text-blue-600" />
                        <div>
                          <div className="font-medium">{p.name}</div>
                          <div className="text-xs text-gray-500">
                            {p.active ? "Đang hoạt động" : "Chưa hoạt động"}
                          </div>
                        </div>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        className="bg-white text-gray-700 border border-gray-300 hover:bg-gray-100"
                        onClick={() => {
                          setSelectedPlatform(p.id);
                          setStep(1);
                        }}
                      >
                        Chọn
                      </Button>
                    </div>
                  ))}
                  <div className="flex items-center justify-center">
                    <Button
                      variant="outline"
                      size="sm"
                      className="bg-white text-gray-700 border border-gray-300 hover:bg-gray-100"
                      onClick={() => setStep(1)}
                    >
                      Thêm Kết Nối Mới
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {step === 1 && (
              <div>
                <div className="text-sm text-gray-600 mb-2">Chọn nền tảng bạn muốn triển khai bot</div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <button
                    className={`border rounded-lg p-6 flex flex-col items-center hover:bg-gray-50 ${selectedPlatform === "s_facebook" ? "ring-2 ring-blue-600" : ""}`}
                    onClick={() => { setSelectedPlatform("s_facebook"); setSelectedPlatformName("Facebook"); }}
                  >
                    <Image src="/facebook.svg" alt="Facebook" width={48} height={48} />
                    <div className="font-semibold mt-3">Facebook</div>
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-semibold">Chọn tài khoản</div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={onConnect} className="bg-white">
                      <UserPlus className="w-4 h-4 mr-2" />
                      Kết nối
                    </Button>
                    <Button size="sm" variant="outline" onClick={async () => { if (selectedPlatform) { setLoading(true); try { const acc = await getSocialAccounts(selectedPlatform); setAccounts(acc.data || []); } finally { setLoading(false); } } }} className="bg-white">Làm mới</Button>
                  </div>
                </div>
                <div className="space-y-2">
                  {accounts.map((a, idx) => (
                    <label key={String(a.id)} className={`flex items-center justify-between border border-gray-200 rounded-lg p-4 cursor-pointer bg-white ${String(selectedAccount) === String(a.id) ? "ring-2 ring-blue-600" : ""}`}>
                      <div className="flex items-center gap-3">
                        {a.avatar_url ? (
                          <Image src={a.avatar_url} alt={a.name} width={36} height={36} className="rounded-full" />
                        ) : (
                          <div className="w-9 h-9 rounded-full bg-gray-200" />
                        )}
                        <div>
                          <div className="font-medium">{idx + 1}. {a.name}</div>
                          <div className="text-xs text-gray-500">Đã kết nối</div>
                        </div>
                      </div>
                      <input type="radio" checked={String(selectedAccount) === String(a.id)} onChange={() => { setSelectedAccount(String(a.id)); setSelectedAccountName(a.name); }} />
                    </label>
                  ))}
                  {accounts.length === 0 && (
                    <div className="text-sm text-gray-600">Chưa có tài khoản được đồng bộ.</div>
                  )}
                </div>
              </div>
            )}

            {step === 3 && (
              <div>
                <div className="text-sm font-semibold mb-2">Chọn trang</div>
                <div className="space-y-2">
                    {pages.map((p, idx) => (
                    <label key={String(p.id)} className={`flex items-center justify-between border border-gray-200 rounded-lg p-4 cursor-pointer bg-white ${p.is_connected ? "bg-green-50" : ""} ${String(selectedPage) === String(p.id) ? "ring-2 ring-blue-600" : ""}`}>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-gray-200" />
                        <div>
                          <div className="font-medium">{idx + 1}. {p.name || String(p.id) || ""}</div>
                          <div className="text-xs text-gray-500">{p.is_connected ? "Đã kết nối" : "Chưa kết nối"}</div>
                        </div>
                      </div>
                      <input type="radio" checked={String(selectedPage) === String(p.id)} onChange={() => { setSelectedPage(String(p.id)); setSelectedPageName(p.name || String(p.id) || ""); }} />
                    </label>
                  ))}
                  {pages.length === 0 && (
                    <div className="text-sm text-gray-600">Chưa có trang khả dụng.</div>
                  )}
                </div>
              </div>
            )}

            {step === 4 && (
              <div>
                <div className="text-sm font-semibold mb-2">Kiểm tra Bot</div>
                <div className="border border-gray-200 rounded-lg p-4 bg-white">
                  <div className="space-y-2 max-h-60 overflow-auto">
                    {testMessages.map((m, i) => (
                      <div key={i} className={`text-sm ${m.from === "user" ? "text-gray-800" : "text-blue-700"}`}>{m.text}</div>
                    ))}
                    {testMessages.length === 0 && (
                      <div className="text-sm text-gray-600">Xin chào! Tôi có thể giúp gì cho bạn?</div>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <Input placeholder="Nhập tin nhắn kiểm thử của bạn..." value={testInput} onChange={(e) => setTestInput(e.target.value)} className="border-gray-300 focus:border-blue-500 focus:ring-blue-500" />
                    <Button onClick={sendTest} className="bg-blue-600 text-white hover:bg-blue-700">Gửi</Button>
                  </div>
                </div>
              </div>
            )}

            {step === 5 && (
              <div>
                <div className="text-lg font-semibold mb-3">Triển khai Bot</div>
                <div className="rounded-lg border border-gray-200 p-4 bg-white">
                  <div className="text-sm font-semibold mb-2">Tổng quan triển khai</div>
                  <div className="grid grid-cols-2 gap-y-2 text-sm">
                    <div>Nền tảng:</div>
                    <div className="text-right">{selectedPlatformName || "Facebook"}</div>
                    <div>Tài khoản:</div>
                    <div className="text-right">{selectedAccountName}</div>
                    <div>Trang:</div>
                    <div className="text-right">{selectedPageName}</div>
                  </div>
                </div>
                {deployed && (
                  <div className="mt-3 bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 text-sm">Triển khai bot thành công!</div>
                )}
                <div className="mt-4 rounded-lg border p-4">
                  <div className="text-sm font-semibold mb-2">Trạng thái Bot</div>
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-600">Bật/tắt bot trên Facebook</div>
                    <button className="w-11 h-6 rounded-full bg-blue-600 relative">
                      <span className="absolute left-6 top-0.5 w-5 h-5 rounded-full bg-white" />
                    </button>
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <Button variant="outline" className="bg-white" onClick={() => setStep(4)}>Quay lại</Button>
                  <Button className="bg-blue-600 text-white hover:bg-blue-700" onClick={onClose}>Hoàn thành</Button>
                </div>
              </div>
            )}

            {loading && (
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Loader2 className="w-4 h-4 animate-spin" />
                Đang tải...
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <Button variant="outline" onClick={onBack} disabled={deploying || step === 0} className="bg-white">Quay lại</Button>
              <Button onClick={onNext} disabled={deploying || !canNext} className="bg-blue-600 text-white hover:bg-blue-700">
                {deploying ? (
                  <span className="flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Đang triển khai</span>
                ) : (
                  "Tiếp theo"
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
