"use client";
import { useEffect, useState } from 'react';
import { StatCard } from '@/components/stat-card';
import { getBots, getDocuments, getSocialAccounts, type Bot } from '@/lib/api';

export default function DashboardPage() {
  const [botsTotal, setBotsTotal] = useState(0);
  const [botsActive, setBotsActive] = useState(0);
  const [socialTotal, setSocialTotal] = useState(0);
  const [knowledgeTotal, setKnowledgeTotal] = useState(0);

  useEffect(() => {
    const SOCIAL_ID = 's_facebook';
    const load = async () => {
      try {
        const [botsRes, socialRes, docsRes] = await Promise.all([
          getBots(),
          getSocialAccounts(SOCIAL_ID),
          getDocuments(),
        ]);
        const bots: Bot[] = botsRes?.data || [];
        setBotsTotal(bots.length);
        setBotsActive(bots.filter((b) => (b.status || '').toLowerCase() === 'active').length);
        setSocialTotal((socialRes?.data || []).length);
        setKnowledgeTotal((docsRes?.data || []).length);
      } catch {}
    };
    load();
  }, []);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Overview Dashboard</h1>
      <p className="text-gray-500 mb-8">Real-time insights into your AI sales and customer engagement</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Bots" total={botsTotal} active={botsActive} percentage={0} />
        <StatCard title="Social Accounts" total={socialTotal} percentage={0} />
        <StatCard title="Knowledge" total={knowledgeTotal} percentage={0} />
        <StatCard title="Chat" total={0} percentage={0} />
        <StatCard title="Feedback" total={0} percentage={0} />
      </div>
    </div>
  );
}