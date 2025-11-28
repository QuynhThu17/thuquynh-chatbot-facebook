import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getCurrentUser,
  getAvatarInfo,
  getBots,
  activateBot,
  deactivateBot,
  deleteBot,
  getSocialAccounts,
  getIdentities,
  copyIdentity,
  deleteIdentity,
  getProcedures,
  updateProcedure,
  deleteProcedure,
  copyProcedure,
  getHistories,
  getHistorySessions,
  getNotifications,
  markNotificationRead,
  markNotificationUnread,
  deleteNotification,
  getSocialPages,
  getSocialPageById,
  getDocuments,
  uploadAvatar,
  updateAvatar,
} from "./api";

export function useCurrentUserQuery() {
  return useQuery({ queryKey: ["auth", "me"], queryFn: async () => (await getCurrentUser()).data, staleTime: 10 * 60 * 1000 });
}

export function useAvatarInfoQuery() {
  return useQuery({ queryKey: ["avatar", "info"], queryFn: async () => (await getAvatarInfo()).data, staleTime: 30 * 60 * 1000 });
}

export function useBotsQuery() {
  return useQuery({ queryKey: ["bots", "list"], queryFn: async () => (await getBots()).data, staleTime: 5 * 60 * 1000, placeholderData: (prev) => prev });
}

export function useSocialAccountsQuery(socialId: string | number) {
  return useQuery({ queryKey: ["social", "accounts", String(socialId)], queryFn: async () => (await getSocialAccounts(socialId)).data, staleTime: 5 * 60 * 1000, placeholderData: (prev) => prev });
}

export function useActivateBotMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await activateBot(id)).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["bots", "list"] }); } });
}

export function useDeactivateBotMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await deactivateBot(id)).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["bots", "list"] }); } });
}

export function useDeleteBotMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await deleteBot(id)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["bots", "list"] }); } });
}

export function useIdentitiesQuery() {
  return useQuery({ queryKey: ["identities", "list"], queryFn: async () => (await getIdentities()).data, placeholderData: (prev) => prev });
}

export function useCopyIdentityMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await copyIdentity(id)).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["identities", "list"] }); } });
}

export function useDeleteIdentityMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await deleteIdentity(id)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["identities", "list"] }); } });
}

export function useProceduresQuery() {
  return useQuery({ queryKey: ["procedures", "list"], queryFn: async () => (await getProcedures()).data, placeholderData: (prev) => prev });
}

export function useUpdateProcedureMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (payload: { id: string | number; title: string; description: string }) => (await updateProcedure(payload.id, { title: payload.title, description: payload.description })).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["procedures", "list"] }); } });
}

export function useCopyProcedureMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await copyProcedure(id)).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["procedures", "list"] }); } });
}

export function useDeleteProcedureMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await deleteProcedure(id)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["procedures", "list"] }); } });
}

export function useHistorySessionsQuery() {
  return useQuery({ queryKey: ["crm", "sessions"], queryFn: async () => (await getHistorySessions({ limit: 20 })).data });
}

export function useHistoriesQuery(params: { social_page_id?: string | number; bot_id?: string | number; session_id?: string | number; limit?: number }) {
  const p = { ...params };
  const keyParts = [String(p.session_id || ""), String(p.social_page_id || ""), String(p.bot_id || ""), String(p.limit || 50)];
  return useQuery({ queryKey: ["crm", "histories", ...keyParts], queryFn: async () => (await getHistories({ session_id: p.session_id ? String(p.session_id) : undefined, social_page_id: p.social_page_id, bot_id: p.bot_id, limit: p.limit ?? 50 })).data, placeholderData: (prev) => prev });
}

export function useSocialPageInfoQuery(social_id: string | number | undefined, social_page_id: string | number | undefined) {
  const sid = social_id ? String(social_id) : undefined;
  const pid = social_page_id ? String(social_page_id) : undefined;
  return useQuery({ queryKey: ["social", "page", sid || "", pid || ""], queryFn: async () => (await getSocialPageById(sid!, pid!)).data, enabled: !!sid && !!pid });
}

export function useNotificationsQuery() {
  return useQuery({ queryKey: ["notifications", "list"], queryFn: async () => (await getNotifications({ limit: 50 })).data });
}

export function useMarkNotificationReadMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await markNotificationRead(id)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["notifications", "list"] }); } });
}

export function useMarkNotificationUnreadMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await markNotificationUnread(id)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["notifications", "list"] }); } });
}

export function useDeleteNotificationMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (id: string | number) => (await deleteNotification(id)), onSuccess: () => { qc.invalidateQueries({ queryKey: ["notifications", "list"] }); } });
}

export function useSocialPagesQuery(social_id: string | number, account_id: string | number) {
  return useQuery({ queryKey: ["social", "pages", String(social_id), String(account_id)], queryFn: async () => (await getSocialPages(social_id, account_id)).data, placeholderData: (prev) => prev });
}

export function useDocumentsQuery() {
  return useQuery({ queryKey: ["documents", "list"], queryFn: async () => (await getDocuments()).data, placeholderData: (prev) => prev });
}

export function useUploadAvatarMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (file: File) => (await uploadAvatar(file)).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["avatar", "info"] }); } });
}

export function useUpdateAvatarMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (avatar_url: string) => (await updateAvatar(avatar_url)).data, onSuccess: () => { qc.invalidateQueries({ queryKey: ["avatar", "info"] }); } });
}
