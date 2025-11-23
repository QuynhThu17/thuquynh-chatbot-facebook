import { StatCard } from '@/components/stat-card';

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Overview Dashboard</h1>
      <p className="text-gray-500 mb-8">Real-time insights into your AI sales and customer engagement</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Bots" total={15} active={3} newCount={1} percentage={100} />
        <StatCard title="Social Accounts" total={1} newCount={0} percentage={0} />
        <StatCard title="Customers" total={14} newCount={0} percentage={0} />
        <StatCard title="Orders" total={4} newCount={4} percentage={100} />
        <StatCard title="Knowledge" total={9} newCount={6} percentage={500} />
        <StatCard title="Chat" total={3} percentage={-25} />
        <StatCard title="Feedback" total={0} percentage={0} />
      </div>
    </div>
  );
}