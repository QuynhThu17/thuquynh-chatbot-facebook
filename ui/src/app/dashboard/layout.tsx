import { Sidebar } from '@/components/sidebar';
import { Header } from '@/components/header';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen w-full bg-white text-black flex">
      <Sidebar />
      <div className="flex flex-col flex-1">
        <Header />
        <main className="p-8">
          {children}
        </main>
      </div>
    </div>
  );
}