"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getAccessToken } from "./auth-storage";

const PUBLIC_PATHS = new Set([
  "/",
  "/auth/login",
  "/auth/register",
  "/_not-found",
]);

export default function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.has(pathname || "/");
  const allowed = isPublic || !!getAccessToken();

  useEffect(() => {
    if (!allowed) {
      const next = encodeURIComponent(pathname || "/");
      router.replace(`/auth/login?next=${next}`);
    }
  }, [allowed, pathname, router]);

  return children;
}