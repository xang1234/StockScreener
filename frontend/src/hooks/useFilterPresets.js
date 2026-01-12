/**
 * React Query hook for filter preset management.
 * Provides queries and mutations for CRUD operations on filter presets.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getFilterPresets,
  createFilterPreset,
  updateFilterPreset,
  deleteFilterPreset,
  reorderFilterPresets,
} from '../api/filterPresets';

// Query keys
export const filterPresetKeys = {
  all: ['filterPresets'],
  list: () => [...filterPresetKeys.all, 'list'],
};

/**
 * Hook for managing filter presets.
 * @returns {Object} Query and mutation functions for filter presets
 */
export const useFilterPresets = () => {
  const queryClient = useQueryClient();

  // Query to fetch all presets
  const presetsQuery = useQuery({
    queryKey: filterPresetKeys.list(),
    queryFn: getFilterPresets,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Mutation to create a preset
  const createMutation = useMutation({
    mutationFn: createFilterPreset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: filterPresetKeys.all });
    },
  });

  // Mutation to update a preset
  const updateMutation = useMutation({
    mutationFn: ({ presetId, updates }) => updateFilterPreset(presetId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: filterPresetKeys.all });
    },
  });

  // Mutation to delete a preset
  const deleteMutation = useMutation({
    mutationFn: deleteFilterPreset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: filterPresetKeys.all });
    },
  });

  // Mutation to reorder presets
  const reorderMutation = useMutation({
    mutationFn: reorderFilterPresets,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: filterPresetKeys.all });
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

export default useFilterPresets;
