import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCurrentUser, getAvatarInfo, getBots, activateBot, deactivateBot, deleteBot, getSocialAccounts } from "./api";

export function useCurrentUserQuery() {
  return useQuery({ queryKey: ["auth", "me"], queryFn: async () => (await getCurrentUser()).data, staleTime: 10 * 60 * 1000 });
}

export function useAvatarInfoQuery() {
  return useQuery({ queryKey: ["avatar", "info"], queryFn: async () => (await getAvatarInfo()).data, staleTime: 30 * 60 * 1000 });
}

export function useBotsQuery() {
  return useQuery({ queryKey: ["bots", "list"], queryFn: async () => (await getBots()).data, staleTime: 5 * 60 * 1000 });
}

export function useSocialAccountsQuery(socialId: string | number) {
  return useQuery({ queryKey: ["social", "accounts", String(socialId)], queryFn: async () => (await getSocialAccounts(socialId)).data, staleTime: 5 * 60 * 1000 });
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
