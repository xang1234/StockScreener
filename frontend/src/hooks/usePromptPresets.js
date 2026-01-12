/**
 * React Query hook for prompt preset management.
 * Provides queries and mutations for CRUD operations on prompt presets.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPromptPresets,
  createPromptPreset,
  updatePromptPreset,
  deletePromptPreset,
  reorderPromptPresets,
} from '../api/promptPresets';

// Query keys
export const promptPresetKeys = {
  all: ['promptPresets'],
  list: () => [...promptPresetKeys.all, 'list'],
};

/**
 * Hook for managing prompt presets.
 * @returns {Object} Query and mutation functions for prompt presets
 */
export const usePromptPresets = () => {
  const queryClient = useQueryClient();

  // Query to fetch all presets
  const presetsQuery = useQuery({
    queryKey: promptPresetKeys.list(),
    queryFn: getPromptPresets,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Mutation to create a preset
  const createMutation = useMutation({
    mutationFn: createPromptPreset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptPresetKeys.all });
    },
  });

  // Mutation to update a preset
  const updateMutation = useMutation({
    mutationFn: ({ presetId, updates }) => updatePromptPreset(presetId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptPresetKeys.all });
    },
  });

  // Mutation to delete a preset
  const deleteMutation = useMutation({
    mutationFn: deletePromptPreset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptPresetKeys.all });
    },
  });

  // Mutation to reorder presets
  const reorderMutation = useMutation({
    mutationFn: reorderPromptPresets,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptPresetKeys.all });
    },
  });

  return {
    // Query data
    presets: presetsQuery.data?.presets || [],
    isLoading: presetsQuery.isLoading,
    error: presetsQuery.error,

    // Mutations
    createPreset: createMutation.mutate,
    createPresetAsync: createMutation.mutateAsync,
    isCreating: createMutation.isPending,

    updatePreset: updateMutation.mutate,
    updatePresetAsync: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,

    deletePreset: deleteMutation.mutate,
    deletePresetAsync: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,

    reorderPresets: reorderMutation.mutate,
    isReordering: reorderMutation.isPending,

    // Refetch
    refetch: presetsQuery.refetch,
  };
};

export default usePromptPresets;
