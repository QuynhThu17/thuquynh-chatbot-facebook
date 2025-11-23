"use client";
import { useEffect, useState, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { Mail, Lock, Loader2, GraduationCap, Sparkles } from "lucide-react";
import { login } from "@/lib/api";
import { AFTER_LOGIN_MAIN_ROUTE } from "../register/page";

export default function LoginPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = () => {
    if (!identifier.trim()) return "Vui lòng nhập email hoặc username";
    if (!password) return "Vui lòng nhập mật khẩu";
    return null;
  };

  useEffect(() => {
    const raw = typeof window !== "undefined" ? sessionStorage.getItem("prefill_login") : null;
    if (!raw) return;
    try {
      const obj = JSON.parse(raw);
      if (obj && obj.email && obj.password && Date.now() - obj.createdAt < obj.ttlMs) {
        setIdentifier(obj.email);
        setPassword(obj.password);
      }
    } catch {}
    finally {
      sessionStorage.removeItem("prefill_login");
    }
  }, []);

  const generateToken = (): string => {
    try {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    } catch {
      return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
    }
  };

  const persistSession = (email: string, rememberFlag: boolean): void => {
    const session = {
      email,
      token: generateToken(),
      createdAt: Date.now(),
      expiresAt: Date.now() + (rememberFlag ? 7 * 24 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000),
    };
    const storage = rememberFlag ? localStorage : sessionStorage;
    storage.setItem("auth_session", JSON.stringify(session));
  };

  const onSubmit = async () => {
    const err = validate();
    if (err) {
      setError(err);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Determine if identifier is email or username
      const isEmail = identifier.includes('@');
      await login({
        [isEmail ? 'email' : 'username']: identifier,
        password: password
      });
      
      // Login successful if no error was thrown
      persistSession(identifier, remember);
      router.replace(AFTER_LOGIN_MAIN_ROUTE);
    } catch (err: any) {
      console.error("Login failed:", err);
      setError(err.message || "Đăng nhập không thành công, vui lòng thử lại");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
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

      <div className="relative flex min-h-screen items-center justify-center p-4">
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

          {/* Login card */}
          <div className="backdrop-blur-xl bg-white/10 rounded-3xl shadow-2xl border border-white/20 p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-semibold text-white mb-1">Đăng nhập</h2>
              <p className="text-blue-200/70 text-sm">Chào mừng bạn quay trở lại</p>
            </div>

            {error && (
              <div className="mb-6 rounded-xl border border-red-400/50 bg-red-500/10 backdrop-blur-sm p-4 text-sm text-red-200 animate-shake">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-red-400 rounded-full"></div>
                  {error}
                </div>
              </div>
            )}

            <div className="space-y-5">
              {/* Email input */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Email/Username</label>
                <div className="relative group">
                  <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3.5 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="email hoặc username"
                  />
                </div>
              </div>

              {/* Password input */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-blue-100">Mật khẩu</label>
                <div className="relative group">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-blue-300/60 group-focus-within:text-yellow-400 transition-colors" />
                  <input
                    className="w-full pl-12 pr-4 py-3.5 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl text-white placeholder:text-blue-300/40 focus:outline-none focus:ring-2 focus:ring-yellow-400/50 focus:border-yellow-400/50 transition-all"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Nhập mật khẩu"
                  />
                </div>
              </div>

              {/* Remember & Forgot */}
              <div className="flex items-center justify-between text-sm">
                <label className="inline-flex items-center gap-2 text-blue-100 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="w-4 h-4 rounded border-white/20 bg-white/10 text-yellow-400 focus:ring-yellow-400/50 focus:ring-offset-0 cursor-pointer"
                  />
                  <span className="group-hover:text-white transition-colors">Ghi nhớ đăng nhập</span>
                </label>
                <a href="#" className="text-yellow-400 hover:text-yellow-300 transition-colors font-medium">
                  Quên mật khẩu?
                </a>
              </div>

              {/* Login button */}
              <button
                className="w-full py-3.5 bg-gradient-to-r from-yellow-400 to-yellow-500 hover:from-yellow-500 hover:to-yellow-600 text-blue-900 font-semibold rounded-xl shadow-lg shadow-yellow-500/30 hover:shadow-yellow-500/50 transition-all transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
                onClick={onSubmit}
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Đang đăng nhập...
                  </span>
                ) : (
                  "Đăng nhập"
                )}
              </button>

              {/* Register link */}
              <div className="text-center text-sm text-blue-200/70 pt-2">
                Chưa có tài khoản?{" "}
                <a href="/auth/register" className="text-yellow-400 hover:text-yellow-300 font-medium transition-colors">
                  Đăng ký ngay
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