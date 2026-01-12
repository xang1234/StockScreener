/**
 * Watchlist Table Component
 *
 * Displays stocks in a watchlist with:
 * - RS sparkline (30-day)
 * - Price sparkline (30-day)
 * - Price change bars for 1d, 5d, 2w, 1m, 3m, 6m, 12m
 * - Delete button per row
 *
 * Simpler than ThemeTable (no subgroups).
 */
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  IconButton,
  Paper,
  Tooltip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RSSparkline from '../Scan/RSSparkline';
import PriceSparkline from '../Scan/PriceSparkline';
import PriceChangeBar from './PriceChangeBar';
import { removeItem } from '../../api/userWatchlists';

const PRICE_PERIODS = [
  { key: '1d', label: '1D' },
  { key: '5d', label: '5D' },
  { key: '2w', label: '2W' },
  { key: '1m', label: '1M' },
  { key: '3m', label: '3M' },
  { key: '6m', label: '6M' },
  { key: '12m', label: '12M' },
];

function WatchlistTable({ watchlistData, onRefresh, onOpenChart }) {
  const [hoveredRow, setHoveredRow] = useState(null);
  const queryClient = useQueryClient();

  const removeMutation = useMutation({
    mutationFn: removeItem,
    onSuccess: () => {
      queryClient.invalidateQueries(['userWatchlistData', watchlistData.id]);
      if (onRefresh) onRefresh();
    },
  });

  const handleRemove = (e, itemId) => {
    e.stopPropagation();
    removeMutation.mutate(itemId);
  };

  const { items, price_change_bounds } = watchlistData;

  if (!items || items.length === 0) {
    return (
      <Box textAlign="center" py={4}>
        <Typography color="text.secondary">
          No stocks in this watchlist yet. Add stocks from scan results, themes, or peer tables.
        </Typography>
      </Box>
    );
  }

  return (
    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 'calc(100vh - 180px)' }}>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow sx={{ '& th': { py: 0.5, fontSize: '0.75rem' } }}>
            <TableCell width={28} sx={{ bgcolor: 'background.paper', px: 0.5 }}></TableCell>
            <TableCell sx={{ bgcolor: 'background.paper', width: 55, maxWidth: 55, px: 0.5 }}>Symbol</TableCell>
            <TableCell sx={{ bgcolor: 'background.paper', width: 150, maxWidth: 150, px: 0.5 }}>Company</TableCell>
            <TableCell align="center" sx={{ bgcolor: 'background.paper', width: 110 }}>
              RS (30d)
            </TableCell>
            <TableCell align="center" sx={{ bgcolor: 'background.paper', width: 110 }}>
              Price (30d)
            </TableCell>
            {PRICE_PERIODS.map((period) => (
              <TableCell
                key={period.key}
                align="center"
                sx={{ bgcolor: 'background.paper', width: 70, px: 0.25 }}
              >
                {period.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((stock) => (
            <TableRow
              key={stock.id}
              hover
              onClick={() => onOpenChart && onOpenChart(stock.symbol)}
              sx={{ '& td': { py: 0.25 }, cursor: onOpenChart ? 'pointer' : 'default' }}
              onMouseEnter={() => setHoveredRow(stock.id)}
              onMouseLeave={() => setHoveredRow(null)}
            >
              <TableCell width={28} sx={{ py: 0.25, px: 0.5 }}>
                {hoveredRow === stock.id && (
                  <Tooltip title="Remove from watchlist">
                    <IconButton
                      size="small"
                      onClick={(e) => handleRemove(e, stock.id)}
                      sx={{ p: 0.25, opacity: 0.7, '&:hover': { opacity: 1 } }}
                    >
                      <DeleteIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                )}
              </TableCell>
              <TableCell sx={{ py: 0.25, px: 0.5, width: 55, maxWidth: 55 }}>
                <Typography variant="body2" fontWeight={500} sx={{ fontSize: '0.75rem' }}>
                  {stock.symbol}
                </Typography>
              </TableCell>
              <TableCell sx={{ py: 0.25, px: 0.5, maxWidth: 150, overflow: 'hidden' }}>
                <Typography
                  variant="caption"
                  sx={{
                    fontSize: '0.6rem',
                    display: 'block',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={stock.company_name || ''}
                >
                  {stock.company_name || '-'}
                </Typography>
              </TableCell>
              <TableCell align="center" sx={{ p: '2px' }}>
                <RSSparkline
                  data={stock.rs_data}
                  trend={stock.rs_trend}
                  width={100}
                  height={24}
                />
              </TableCell>
              <TableCell align="center" sx={{ p: '2px' }}>
                <PriceSparkline
                  data={stock.price_data}
                  trend={stock.price_trend}
                  change1d={stock.change_1d}
                  width={110}
                  height={22}
                  showChange={false}
                />
              </TableCell>
              {PRICE_PERIODS.map((period) => {
                const changeKey = `change_${period.key}`;
                const change = stock[changeKey];
                const bounds = price_change_bounds[period.key] || { min: 0, max: 0 };
                return (
                  <TableCell key={period.key} align="center" sx={{ p: '1px 2px' }}>
                    <PriceChangeBar
                      value={change}
                      min={bounds.min}
                      max={bounds.max}
                      width={65}
                      height={16}
                    />
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default WatchlistTable;
