"use client";
import { useMemo } from 'react';
import { StatCard } from '@/components/stat-card';
import { useBotsQuery, useIdentitiesQuery, useProceduresQuery, useDocumentsQuery, useSocialAccountsQuery } from '@/lib/queries';
import type { Bot, Identity, Procedure, KnowledgeDocument, SocialAccount } from '@/lib/api';

export default function DashboardPage() {
  const botsQuery = useBotsQuery();
  const identitiesQuery = useIdentitiesQuery();
  const proceduresQuery = useProceduresQuery();
  const documentsQuery = useDocumentsQuery();
  const accountsQuery = useSocialAccountsQuery('s_facebook');

  const bots: Bot[] = (botsQuery.data as Bot[]) || [];
  const identities: Identity[] = (identitiesQuery.data as Identity[]) || [];
  const procedures: Procedure[] = (proceduresQuery.data as Procedure[]) || [];
  const documents: KnowledgeDocument[] = (documentsQuery.data as KnowledgeDocument[]) || [];
  const accounts: SocialAccount[] = (accountsQuery.data as SocialAccount[]) || [];

  const botsTotal = bots.length;
  const botsActive = useMemo(() => bots.filter((b) => (b.status || '').toLowerCase() === 'active').length, [bots]);
  const socialTotal = accounts.length;
  const knowledgeTotal = documents.length;
  const identitiesTotal = identities.length;
  const workflowTotal = procedures.length;

  return (
    <div>
      <h1 className="text-3xl font-bold mb-2">Overview Dashboard</h1>
      <p className="text-gray-500 mb-8">Real-time insights into your AI sales and customer engagement</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Bots" total={botsTotal} active={botsActive} percentage={0} />
        <StatCard title="Identities" total={identitiesTotal} percentage={0} />
        <StatCard title="Workflow" total={workflowTotal} percentage={0} />
        <StatCard title="Social Accounts" total={socialTotal} percentage={0} />
        <StatCard title="Knowledge" total={knowledgeTotal} percentage={0} />
        <StatCard title="Chats" total={0} percentage={0} />
        <StatCard title="Feedback" total={0} percentage={0} />
      </div>
    </div>
  );
}
