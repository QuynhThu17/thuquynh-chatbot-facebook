"use client";
import { Bell, MessageSquare, Search, ChevronDown, LogOut, Settings } from 'lucide-react';
import Image from 'next/image';
import { useState } from 'react';
import { logout } from '@/lib/api';
import { useCurrentUserQuery, useAvatarInfoQuery } from '@/lib/queries';

export function Header() {
  const [open, setOpen] = useState(false);
  const u = useCurrentUserQuery();
  const a = useAvatarInfoQuery();
  const d = (u.data as any) || {};
  const name = d.name || d.username || d.full_name || 'User';
  const role = d.role || d.user_role || d.type || '';
  const email = d.email || '';
  const avatarUrl = ((a.data as any)?.avatar_url || (a.data as any)?.url) as string | undefined;

  function initials(text: string) {
    const s = (text || '').trim();
    if (!s) return 'U';
    const parts = s.split(/\s+/);
    const first = parts[0]?.[0] || 'U';
    return first.toUpperCase();
  }

  async function onLogout() {
    try { await logout(); } catch {}
    if (typeof window !== 'undefined') window.location.href = '/auth/login';
  }

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8">
      <div className="flex items-center space-x-4">
        <button className="p-2 rounded-full hover:bg-gray-100">
          <Search className="w-5 h-5 text-gray-500" />
        </button>
        <input type="text" placeholder="Search..." className="bg-transparent focus:outline-none" />
      </div>
      <div className="flex items-center space-x-4 relative">
        <button className="p-2 rounded-full hover:bg-gray-100">
          <MessageSquare className="w-5 h-5 text-gray-500" />
        </button>
        <button className="p-2 rounded-full hover:bg-gray-100">
          <Bell className="w-5 h-5 text-gray-500" />
        </button>
        <button onClick={() => setOpen(v => !v)} className="p-2 rounded-full hover:bg-gray-100 flex items-center space-x-2">
          {avatarUrl ? (
            <Image src={avatarUrl} alt={name} width={28} height={28} className="rounded-full" unoptimized />
          ) : (
            <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center">
              <span className="text-xs font-semibold text-gray-700">{initials(name)}</span>
            </div>
          )}
          <div className="hidden md:block text-left">
            <div className="text-sm font-medium leading-tight max-w-[140px] truncate">{name || 'User'}</div>
            {role && <div className="text-xs text-gray-500">{role}</div>}
          </div>
          <ChevronDown className="w-4 h-4 text-gray-500" />
        </button>

        {open && (
          <div className="absolute right-0 top-12 w-64 bg-white border rounded-xl shadow-lg z-50">
            <div className="px-4 py-3">
              <div className="font-semibold truncate">{name}</div>
              {email && <div className="text-sm text-gray-600 truncate">{email}</div>}
            </div>
            <div className="border-t">
              <button onClick={() => { if (typeof window !== 'undefined') window.location.href = '/settings'; }} className="w-full flex items-center px-4 py-2 hover:bg-gray-50">
                <Settings className="w-4 h-4 mr-2" />
                <span>Cài đặt tài khoản</span>
              </button>
              <button onClick={onLogout} className="w-full flex items-center px-4 py-2 text-red-600 hover:bg-red-50">
                <LogOut className="w-4 h-4 mr-2" />
                <span>Đăng xuất</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
