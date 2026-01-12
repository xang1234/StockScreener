/**
 * CacheStatus Component
 *
 * Displays cache health status for fundamentals and price data.
 * Provides manual refresh buttons to trigger cache warmup tasks.
 *
 * Features:
 * - Auto-refresh stats every 60 seconds
 * - Relative time display ("2 hours ago")
 * - Color-coded freshness indicators
 * - Manual refresh buttons with loading states
 * - Confirmation dialog for expensive operations
 * - Success/error notifications
 */
import React, { useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Box,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Snackbar,
  Alert,
  IconButton
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getCacheStats,
  triggerFundamentalsRefresh,
  triggerPriceRefresh,
  getStalenessStatus,
  forceRefreshPriceCache
} from '../../api/cache';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import RefreshIcon from '@mui/icons-material/Refresh';

/**
 * Calculate relative time string from ISO timestamp.
 * Examples: "2 hours ago", "3 days ago", "just now"
 */
const getRelativeTime = (isoTimestamp) => {
  if (!isoTimestamp || isoTimestamp === 'N/A') {
    return 'Never';
  }

  try {
    const date = new Date(isoTimestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  } catch (error) {
    return 'Unknown';
  }
};

/**
 * Get freshness status and color for fundamentals cache.
 * - Green (Fresh): < 3 days
 * - Yellow (Stale): 3-7 days
 * - Red (Very Stale): > 7 days
 */
const getFundamentalsFreshness = (lastUpdate) => {
  if (!lastUpdate || lastUpdate === 'Never') {
    return { status: 'No Data', color: 'error', icon: <ErrorIcon /> };
  }

  try {
    const date = new Date(lastUpdate);
    const now = new Date();
    const diffDays = Math.floor((now - date) / 86400000);

    if (diffDays < 3) {
      return { status: 'Fresh', color: 'success', icon: <CheckCircleIcon /> };
    } else if (diffDays <= 7) {
      return { status: 'Stale', color: 'warning', icon: <WarningIcon /> };
    } else {
      return { status: 'Very Stale', color: 'error', icon: <ErrorIcon /> };
    }
  } catch (error) {
    return { status: 'Error', color: 'error', icon: <ErrorIcon /> };
  }
};

/**
 * Get freshness status and color for price cache.
 * - Green (Fresh): < 1 day
 * - Yellow (Stale): 1-2 days
 * - Red (Very Stale): > 2 days
 */
const getPriceFreshness = (lastUpdate) => {
  if (!lastUpdate || lastUpdate === 'Never' || lastUpdate === 'N/A') {
    return { status: 'No Data', color: 'error', icon: <ErrorIcon /> };
  }

  try {
    const date = new Date(lastUpdate);
    const now = new Date();
    const diffDays = Math.floor((now - date) / 86400000);

    if (diffDays < 1) {
      return { status: 'Fresh', color: 'success', icon: <CheckCircleIcon /> };
    } else if (diffDays <= 2) {
      return { status: 'Stale', color: 'warning', icon: <WarningIcon /> };
    } else {
      return { status: 'Very Stale', color: 'error', icon: <ErrorIcon /> };
    }
  } catch (error) {
    return { status: 'Error', color: 'error', icon: <ErrorIcon /> };
  }
};

export default function CacheStatus() {
  const queryClient = useQueryClient();

  // State for confirmation dialog
  const [confirmDialog, setConfirmDialog] = useState({
    open: false,
    type: null
  });

  // State for notifications
  const [notification, setNotification] = useState({
    open: false,
    message: '',
    severity: 'success'
  });

  // Query cache stats every 60 seconds
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['cacheStats'],
    queryFn: getCacheStats,
    refetchInterval: 60000, // 60 seconds
    staleTime: 30000, // 30 seconds
    retry: 2
  });

  // Query staleness status every 60 seconds
  const { data: stalenessStatus } = useQuery({
    queryKey: ['stalenessStatus'],
    queryFn: getStalenessStatus,
    refetchInterval: 60000, // 60 seconds
    staleTime: 30000, // 30 seconds
    retry: 2
  });

  // Mutation for fundamental refresh
  const fundamentalsMutation = useMutation({
    mutationFn: triggerFundamentalsRefresh,
    onSuccess: (data) => {
      setNotification({
        open: true,
        message: `Fundamentals refresh started`,
        severity: 'success'
      });
      setConfirmDialog({ open: false, type: null });
      setTimeout(() => queryClient.invalidateQueries(['cacheStats']), 5000);
    },
    onError: (error) => {
      setNotification({
        open: true,
        message: `Error: ${error.message}`,
        severity: 'error'
      });
      setConfirmDialog({ open: false, type: null });
    }
  });

  // Mutation for price refresh
  const priceMutation = useMutation({
    mutationFn: triggerPriceRefresh,
    onSuccess: (data) => {
      setNotification({
        open: true,
        message: `Price refresh started`,
        severity: 'success'
      });
      setTimeout(() => queryClient.invalidateQueries(['cacheStats']), 5000);
    },
    onError: (error) => {
      setNotification({
        open: true,
        message: `Error: ${error.message}`,
        severity: 'error'
      });
    }
  });

  // Mutation for force refresh stale intraday data
  const forceRefreshMutation = useMutation({
    mutationFn: (refreshAll = false) => forceRefreshPriceCache({ refreshAll }),
    onSuccess: (data) => {
      if (data.status === 'skipped') {
        setNotification({
          open: true,
          message: data.message || 'No data to refresh',
          severity: 'info'
        });
      } else {
        setNotification({
          open: true,
          message: data.message || 'Refreshing price data...',
          severity: 'success'
        });
      }
      // Refresh staleness status after a delay
      setTimeout(() => {
        queryClient.invalidateQueries(['stalenessStatus']);
        queryClient.invalidateQueries(['cacheStats']);
      }, 5000);
    },
    onError: (error) => {
      setNotification({
        open: true,
        message: `Error: ${error.message}`,
        severity: 'error'
      });
    }
  });

  // Handle refresh button clicks
  const handleRefreshClick = (type, e) => {
    e.stopPropagation();
    if (type === 'fundamentals') {
      setConfirmDialog({ open: true, type: 'fundamentals' });
    } else {
      priceMutation.mutate();
    }
  };

  const handleConfirm = () => {
    if (confirmDialog.type === 'fundamentals') {
      fundamentalsMutation.mutate();
    }
  };

  const handleCancel = () => {
    setConfirmDialog({ open: false, type: null });
  };

  const handleNotificationClose = () => {
    setNotification({ ...notification, open: false });
  };

  // Loading state - show minimal loading
  if (isLoading) {
    return <CircularProgress size={16} />;
  }

  // Error state - show error chip
  if (error) {
    return (
      <Tooltip title="Cache error" arrow>
        <Chip icon={<ErrorIcon />} label="Cache" color="error" size="small" sx={{ height: 20, fontSize: '10px' }} />
      </Tooltip>
    );
  }

  // Extract data
  const fundamentals = stats?.fundamentals || {};
  const prices = stats?.prices || {};
  const hasStaleIntraday = stalenessStatus?.has_stale_data || false;
  const staleCount = stalenessStatus?.stale_intraday_count || 0;

  const fundamentalsFreshness = getFundamentalsFreshness(fundamentals.last_update);
  const priceFreshness = getPriceFreshness(prices.spy_last_update);

  // Handle stale intraday refresh click (only stale symbols)
  const handleStaleRefresh = (e) => {
    e.stopPropagation();
    forceRefreshMutation.mutate(false); // refreshAll = false
  };

  // Handle force refresh ALL click
  const handleForceRefreshAll = (e) => {
    e.stopPropagation();
    forceRefreshMutation.mutate(true); // refreshAll = true
  };

  return (
    <>
      {/* Compact inline cache indicators */}
      <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
        {/* Stale Intraday Data Warning - only shows when stale data exists */}
        {hasStaleIntraday && (
          <Tooltip
            title={
              <Box sx={{ fontSize: '11px' }}>
                <Box sx={{ fontWeight: 600, mb: 0.5, color: '#ff9800' }}>Stale Intraday Data Detected</Box>
                <Box>{staleCount} symbols have data fetched during market hours</Box>
                <Box>that is now outdated (market has closed).</Box>
                <Box sx={{ mt: 0.5 }}>
                  Symbols: {stalenessStatus?.stale_symbols?.slice(0, 5).join(', ')}
                  {staleCount > 5 ? '...' : ''}
                </Box>
                <Box sx={{ mt: 0.5, fontStyle: 'italic', fontWeight: 500 }}>
                  Click to refresh with closing prices
                </Box>
              </Box>
            }
            arrow
          >
            <Chip
              icon={forceRefreshMutation.isPending ? <CircularProgress size={10} /> : <WarningIcon />}
              label={`Stale (${staleCount})`}
              color="warning"
              size="small"
              onClick={handleStaleRefresh}
              sx={{
                height: 20,
                fontSize: '10px',
                cursor: 'pointer',
                '& .MuiChip-icon': { fontSize: 12 },
                animation: 'pulse 2s infinite',
                '@keyframes pulse': {
                  '0%': { opacity: 1 },
                  '50%': { opacity: 0.7 },
                  '100%': { opacity: 1 }
                }
              }}
            />
          </Tooltip>
        )}

        <Tooltip
          title={
            <Box sx={{ fontSize: '11px' }}>
              <Box sx={{ fontWeight: 600, mb: 0.5 }}>Fundamentals: {fundamentalsFreshness.status}</Box>
              <Box>Updated: {getRelativeTime(fundamentals.last_update)}</Box>
              <Box>{fundamentals.cached_count || 0} cached, {fundamentals.fresh_count || 0} fresh</Box>
              <Box sx={{ mt: 0.5, fontStyle: 'italic' }}>Click to refresh</Box>
            </Box>
          }
          arrow
        >
          <Chip
            icon={fundamentalsMutation.isPending ? <CircularProgress size={10} /> : fundamentalsFreshness.icon}
            label="Fund"
            color={fundamentalsFreshness.color}
            size="small"
            onClick={(e) => handleRefreshClick('fundamentals', e)}
            sx={{ height: 20, fontSize: '10px', cursor: 'pointer', '& .MuiChip-icon': { fontSize: 12 } }}
          />
        </Tooltip>

        <Tooltip
          title={
            <Box sx={{ fontSize: '11px' }}>
              <Box sx={{ fontWeight: 600, mb: 0.5 }}>Prices: {priceFreshness.status}</Box>
              <Box>SPY Updated: {getRelativeTime(prices.spy_last_update)}</Box>
              <Box>{prices.total_symbols_cached || 0} symbols cached</Box>
              <Box sx={{ mt: 0.5, fontStyle: 'italic' }}>Click to refresh</Box>
            </Box>
          }
          arrow
        >
          <Chip
            icon={priceMutation.isPending ? <CircularProgress size={10} /> : priceFreshness.icon}
            label="Price"
            color={priceFreshness.color}
            size="small"
            onClick={(e) => handleRefreshClick('prices', e)}
            sx={{ height: 20, fontSize: '10px', cursor: 'pointer', '& .MuiChip-icon': { fontSize: 12 } }}
          />
        </Tooltip>

        {/* Force Refresh Button - always visible */}
        <Tooltip
          title={
            <Box sx={{ fontSize: '11px' }}>
              <Box sx={{ fontWeight: 600, mb: 0.5 }}>Force Refresh All Prices</Box>
              <Box>Re-fetch price data for ALL cached symbols.</Box>
              <Box>Use this to get latest closing prices.</Box>
              {hasStaleIntraday && (
                <Box sx={{ mt: 0.5, color: '#ff9800' }}>
                  {staleCount} symbols have stale intraday data
                </Box>
              )}
            </Box>
          }
          arrow
        >
          <IconButton
            size="small"
            onClick={handleForceRefreshAll}
            disabled={forceRefreshMutation.isPending}
            sx={{
              width: 20,
              height: 20,
              padding: 0,
              '& .MuiSvgIcon-root': { fontSize: 14 }
            }}
          >
            {forceRefreshMutation.isPending ? (
              <CircularProgress size={12} />
            ) : (
              <RefreshIcon color={hasStaleIntraday ? 'warning' : 'action'} />
            )}
          </IconButton>
        </Tooltip>
      </Box>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialog.open} onClose={handleCancel}>
        <DialogTitle sx={{ fontSize: '14px', pb: 1 }}>Refresh Fundamentals?</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: '12px' }}>
            This will refresh data for ~7,000 stocks. Takes ~1 hour.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancel} size="small">Cancel</Button>
          <Button onClick={handleConfirm} variant="contained" size="small">Refresh</Button>
        </DialogActions>
      </Dialog>

      {/* Notification */}
      <Snackbar
        open={notification.open}
        autoHideDuration={3000}
        onClose={handleNotificationClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleNotificationClose} severity={notification.severity} sx={{ fontSize: '11px' }}>
          {notification.message}
        </Alert>
      </Snackbar>
    </>
  );
}
