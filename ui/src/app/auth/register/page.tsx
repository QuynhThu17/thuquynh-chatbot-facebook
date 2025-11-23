"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Mail, Lock, User, Hash, Loader2, GraduationCap, Sparkles, Send, CheckCircle2 } from "lucide-react";
import { register, sendVerificationEmail } from "@/lib/api";

export const AFTER_LOGIN_MAIN_ROUTE = "/";

function validatePassword(pw: string): string | null {
  if (!pw) return "Vui lòng nhập mật khẩu";
  if (pw.length < 8) return "Mật khẩu phải có ít nhất 8 ký tự";
  if (pw.length > 128) return "Mật khẩu không vượt quá 128 ký tự";
  if (!/[A-Z]/.test(pw)) return "Cần ít nhất 1 chữ in hoa";
  if (!/[a-z]/.test(pw)) return "Cần ít nhất 1 chữ thường";
  if (!/\d/.test(pw)) return "Cần ít nhất 1 chữ số";
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(pw))
    return "Cần ít nhất 1 ký tự đặc biệt (!@#$%^&*(),.?\":{}|<>)";
  return null;
}

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const validate = () => {
    if (!name.trim()) return "Vui lòng nhập họ tên";
    if (!email.trim()) return "Vui lòng nhập email";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "Email không hợp lệ";
    const pwErr = validatePassword(password);
    if (pwErr) return pwErr;
    if (password !== confirm) return "Xác nhận mật khẩu không khớp";
    if (!verificationCode.trim()) return "Vui lòng nhập mã xác thực";
    return null;
  };

  const onSendVerification = async () => {
    setError(null);
    setInfo(null);
    if (!email.trim()) {
      setError("Vui lòng nhập email trước khi gửi mã");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Email không hợp lệ");
      return;
    }
    setSending(true);
    try {
      const response = await sendVerificationEmail(email);
      
      if (response.success) {
        setInfo("Đã gửi mã xác thực đến email của bạn!");
      } else {
        setError(response.message || "Gửi mã xác thực thất bại, vui lòng thử lại");
      }
    } catch (error: any) {
      setError(error.message || "Gửi mã xác thực thất bại, vui lòng thử lại");
    } finally {
      setSending(false);
    }
  };

  const onSubmit = async () => {
    const err = validate();
    if (err) {
      setError(err);
      setInfo(null);
      return;
    }
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      // Use actual register API function
      const response = await register({
        name,
        email,
        password,
      });
      
      if (response.success) {
        setInfo("Đăng ký thành công!");
        // Redirect to main page after successful registration
        router.replace(AFTER_LOGIN_MAIN_ROUTE);
      } else {
        setError(response.message || "Đăng ký không thành công");
      }
    } catch (err: any) {
      setError(err.message || "Đăng ký không thành công, vui lòng thử lại");
    } finally {
      setLoading(false);
    }
  };



  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      onSubmit();
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-br from-blue-900 via-blue-800 to-blue-950">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-yellow-400/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute top-60 -left-40 w-96 h-96 bg-blue-400/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
        <div className="absolute -bottom-40 right-1/3 w-80 h-80 bg-yellow-300/10 rounded-full blur-3xl animate-pulse delay-500"></div>
      </div>

      {/* Decorative grid pattern */}
      <div className="absolute inset-0 opacity-5" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px)',
        backgroundSize: '50px 50px'
      }}></div>

      <div className="relative flex min-h-screen items-center justify-center p-4 py-12">
        <div className="w-full max-w-md">
          {/* Logo and branding */}
          <div className="mb-8 text-center">
            <div className="inline-flex items-center justify-center w-20 h-20 mb-4 bg-gradient-to-br from-yellow-400 to-yellow-500 rounded-2xl shadow-2xl shadow-yellow-500/30">
              <GraduationCap className="w-10 h-10 text-blue-900" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2 flex items-center justify-center gap-2">
              HUEAI
              <Sparkles className="w-6 h-6 text-yellow-400 animate-pulse" />
            </h1>
            <p className="text-blue-200/80">Nền tảng AI đa kênh cho doanh nghiệp</p>
          </div>

          {/* Register card */}
          <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-white mb-1">Đăng ký tài khoản</h2>
              <p className="text-blue-200/70 text-sm">Tạo tài khoản mới để bắt đầu</p>
            </div>

            {error && (
              <div className="mb-5 rounded-xl border border-red-400/50 bg-red-500/10 backdrop-blur-sm p-4 text-sm text-red-200 animate-shake">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-red-400 rounded-full"></div>
                  {error}
                </div>
              </div>
            )}

            {info && (
              <div className="mb-5 rounded-xl border border-green-400/50 bg-green-500/10 backdrop-blur-sm p-4 text-sm text-green-200">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-400" />
                  {info}
                </div>
              </div>
            )}

            <div className="space-y-4">
              {/* Name input */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Họ tên</label>
                <div className="relative group">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Nguyễn Văn A"
                  />
                </div>
              </div>

              {/* Email input */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Email</label>
                <div className="relative group">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="email@example.com"
                  />
                </div>
              </div>

              {/* Password input */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Mật khẩu</label>
                <div className="relative group">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all text-sm"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Ít nhất 8 ký tự, hoa, thường, số và ký tự đặc biệt"
                  />
                </div>
              </div>

              {/* Confirm password input */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Xác nhận mật khẩu</label>
                <div className="relative group">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all"
                    type="password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    placeholder="Nhập lại mật khẩu"
                  />
                </div>
              </div>

              {/* Verification code section */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Mã xác thực</label>
                <div className="relative group">
                  <Hash className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Nhập mã từ email"
                  />
                </div>
                
                {/* Send verification button */}
                <button
                  className="w-full py-3 bg-white/10 mt-5 backdrop-blur-sm border border-white/20 hover:bg-white/20 text-blue-100 font-medium rounded-xl transition-all transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex items-center justify-center gap-2"
                  onClick={onSendVerification}
                  disabled={sending}
                >
                  {sending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Đang gửi...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      <span>Gửi email xác thực</span>
                    </>
                  )}
                </button>
              </div>

              {/* Register button */}
              <button
                className="w-full py-3.5 bg-gradient-to-r from-yellow-400 to-yellow-500 hover:from-yellow-500 hover:to-yellow-600 text-blue-900 font-semibold rounded-xl shadow-lg shadow-yellow-500/30 hover:shadow-yellow-500/50 transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none mt-2"
                onClick={onSubmit}
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Đang đăng ký...
                  </span>
                ) : (
                  "Đăng ký"
                )}
              </button>

              {/* Login link */}
              <div className="text-center text-sm text-blue-200/70 pt-2">
                Đã có tài khoản?{" "}
                <a href="/auth/login" className="text-yellow-400 hover:text-yellow-300 font-medium transition-colors">
                  Đăng nhập ngay
                </a>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 text-center text-blue-300/50 text-sm">
            <p>© 2025 HUEAI. All rights reserved.</p>
          </div>
        </div>
      </div>
    </div>
  );
}