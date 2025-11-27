"use client";

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

// SVG Icons
const DashboardIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const BotIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 14v-4c0-1.105.895-2 2-2h4c1.105 0 2 .895 2 2v4M8 14h8m-8 4h8m-4-4v4m8-4v4m-4-4h4M4 14h4m-4-4v4m8-4v4m-4-4h4" />
  </svg>
);

const SocialIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
  </svg>
);

const IdentityIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4z" />
  </svg>
);

const WorkflowIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const KnowledgeIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
  </svg>
);

const HistoryIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const SettingsIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const HelpIcon = ({ className = "w-5 h-5 mr-3" }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') {
      return pathname === '/';
    }
    // Kiểm tra chính xác route, tránh active nhiều tab con cùng lúc
    if (href === '/bots') {
      return pathname === '/bots' || pathname === '/bots/';
    }
    return pathname === href || pathname.startsWith(href + '/');
  };

  const getLinkClassName = (href: string) => {
    const baseClass = "flex items-center px-4 py-2 text-sm font-medium rounded-lg hover:bg-gray-200";
    const activeClass = isActive(href) 
      ? "bg-gray-200 text-gray-900" 
      : "text-gray-700";
    return `${baseClass} ${activeClass}`;
  };

  return (
    <aside className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
      <div className="h-24 flex items-center justify-center border-b border-gray-200">
        <Image src="/logoHUR.jpg" alt="HUEAI Logo" width={60} height={60} />
        <h1 className="text-xl font-bold ml-4">HUEAI</h1>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tổng quan</h2>
        <Link href="/dashboard" className={getLinkClassName("/dashboard")}>
          <DashboardIcon />
          Dashboard
        </Link>
        
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider pt-4">AI & Tự động hóa</h2>
        <Link href="/bots" className={getLinkClassName("/bots")}>
          <BotIcon />
          AI Bots
          <span className="ml-auto bg-green-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">15</span>
        </Link>
        
        <Link href="/bots/identity" className={getLinkClassName("/bots/identity")}>
          <IdentityIcon />
          Danh tính
        </Link>
        
        <Link href="/bots/workflow" className={getLinkClassName("/bots/workflow")}>
          <WorkflowIcon />
          Quy trình
        </Link>
        
        <Link href="/bots/knowledge" className={getLinkClassName("/bots/knowledge")}>
          <KnowledgeIcon />
          Kiến thức
        </Link>
        
        <Link href="/social" className={getLinkClassName("/social")}>
          <SocialIcon />
          Mạng xã hội
          <span className="ml-auto bg-yellow-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">6</span>
        </Link>
        
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider pt-4">Quản lý Lịch sử</h2>
        <Link href="/history" className={getLinkClassName("/history")}>
          <HistoryIcon />
          Lịch sử
          <span className="ml-auto bg-red-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">847</span>
        </Link>
        
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider pt-4">Hệ thống</h2>
        <Link href="/settings" className={getLinkClassName("/settings")}>
          <SettingsIcon />
          Cài đặt
        </Link>
        
        <Link href="#" className={getLinkClassName("/help")}>
          <HelpIcon />
          Trợ giúp & Hỗ trợ
        </Link>
      </nav>
      <div className="p-4 border-t border-gray-200">
        <p className="text-xs text-gray-500">Mang đến cơ hội khai phá tiềm năng đổi mới cho nhà trường</p>
      </div>
    </aside>
  );
}