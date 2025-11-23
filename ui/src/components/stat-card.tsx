import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface StatCardProps {
  title: string;
  total: number;
  active?: number;
  newCount?: number;
  percentage: number;
}

export function StatCard({ title, total, active, newCount, percentage }: StatCardProps) {
  return (
    <div className="bg-gray-50 p-6 rounded-lg">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-3xl font-bold">{total}</p>
        </div>
        <div className={`flex items-center text-sm font-semibold ${percentage >= 0 ? 'text-green-500' : 'text-red-500'}`}>
          {percentage >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
          {Math.abs(percentage)}%
        </div>
      </div>
      {(active !== undefined || newCount !== undefined) && (
        <div className="mt-4 text-xs text-gray-500">
          {active !== undefined && <span><span className="font-bold">Active:</span> {active}</span>}
          {newCount !== undefined && <span className="ml-4"><span className="font-bold">New:</span> {newCount}</span>}
        </div>
      )}
    </div>
  );
}