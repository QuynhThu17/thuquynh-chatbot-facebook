import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  text?: string;
  className?: string;
}

export function LoadingSpinner({ size = "md", text, className = "" }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "w-4 h-4",
    md: "w-8 h-8",
    lg: "w-12 h-12",
  };

  return (
    <div className={`flex items-center justify-center gap-2 ${className}`}>
      <Loader2 className={`${sizeClasses[size]} animate-spin text-yellow-400`} />
      {text && <span className="text-blue-200">{text}</span>}
    </div>
  );
}

interface LoadingOverlayProps {
  text?: string;
  className?: string;
}

export function LoadingOverlay({ text = "Đang tải...", className = "" }: LoadingOverlayProps) {
  return (
    <div className={`fixed inset-0 bg-blue-900/80 backdrop-blur-sm flex items-center justify-center z-50 ${className}`}>
      <div className="text-center backdrop-blur-xl bg-white/10 rounded-3xl p-8 border border-white/20">
        <LoadingSpinner size="lg" />
        <p className="text-blue-200 text-lg mt-4">{text}</p>
      </div>
    </div>
  );
}