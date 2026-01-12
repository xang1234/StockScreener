import { useMemo, memo } from 'react';
import { BarChart, Bar, Cell, ResponsiveContainer, YAxis } from 'recharts';
import { Box, Tooltip } from '@mui/material';

/**
 * RS Sparkline Component
 *
 * Renders a column/bar sparkline showing the RS ratio trend
 * over the last 30 trading days. Mimics Google Sheets SPARKLINE formula:
 * =SPARKLINE(stock_price/SPY_price, {"charttype","column";"color","lightgreen";"highcolor","blue";"lowcolor","red"})
 *
 * Color coding (matching Google Sheets):
 * - Light green bars: All bars (default)
 * - Blue bar: Single highest RS ratio value (peak performance)
 * - Red bar: Single lowest RS ratio value (weakest point)
 */
function RSSparkline({ data, trend, width = 60, height = 20 }) {
  // Transform data for chart - use raw RS ratios like Google Sheets
  const { chartData, domain, maxIndex, minIndex } = useMemo(() => {
    if (!data || !Array.isArray(data) || data.length === 0) {
      return { chartData: [], domain: [0, 1], maxIndex: -1, minIndex: -1 };
    }

    // Use raw RS ratio values (stock_price / SPY_price)
    const chartData = data.map((value, index) => ({
      index,
      value,
    }));

    const values = data;
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);

    // Find indices of max and min values for color highlighting
    const maxIndex = values.indexOf(maxVal);
    const minIndex = values.indexOf(minVal);

    // Add padding to domain for better visualization
    const range = maxVal - minVal || 0.01;
    const padding = range * 0.1;

    return {
      chartData,
      domain: [minVal - padding, maxVal + padding],
      maxIndex,
      minIndex,
    };
  }, [data]);

  // Get trend text and percentage for tooltip
  const tooltipText = useMemo(() => {
    if (!chartData || chartData.length === 0) return 'No RS data';
    const trendText = trend === 1 ? 'Improving' : trend === -1 ? 'Declining' : 'Flat';
    const firstVal = chartData[0]?.value || 1;
    const lastVal = chartData[chartData.length - 1]?.value || 1;
    const change = ((lastVal - firstVal) / firstVal) * 100;
    const sign = change >= 0 ? '+' : '';
    return `RS ${trendText} (${sign}${change.toFixed(1)}% over 30d)`;
  }, [trend, chartData]);

  // No data - show placeholder
  if (!chartData || chartData.length === 0) {
    return (
      <Box
        sx={{
          width,
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'text.disabled',
          fontSize: 10,
        }}
      >
        -
      </Box>
    );
  }

  return (
    <Tooltip
      title={tooltipText}
      arrow
      placement="top"
    >
      <Box sx={{ width, height, cursor: 'pointer' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 1, right: 0, left: 0, bottom: 1 }}
          >
            <YAxis domain={domain} hide />
            <Bar
              dataKey="value"
              maxBarSize={3}
              radius={[1, 1, 0, 0]}
            >
              {chartData.map((entry, index) => {
                // Color coding matching Google Sheets:
                // - Blue: highest value (highcolor)
                // - Red: lowest value (lowcolor)
                // - Light green: all other bars (color)
                let fillColor = '#90EE90'; // lightgreen (default)
                if (index === maxIndex) {
                  fillColor = '#1F97F4'; // blue for highest
                } else if (index === minIndex) {
                  fillColor = '#f44336'; // red for lowest
                }
                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={fillColor}
                    fillOpacity={1.0}
                  />
                );
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Box>
    </Tooltip>
  );
}

// Memoize component - only re-render when data or dimensions change
export default memo(RSSparkline, (prevProps, nextProps) => {
  // Deep compare data arrays
  if (prevProps.data === nextProps.data) return true;
  if (!prevProps.data || !nextProps.data) return false;
  if (prevProps.data.length !== nextProps.data.length) return false;

  // For sparkline data, compare first, last, and length (sufficient for visual comparison)
  return (
    prevProps.data[0] === nextProps.data[0] &&
    prevProps.data[prevProps.data.length - 1] === nextProps.data[nextProps.data.length - 1] &&
    prevProps.trend === nextProps.trend &&
    prevProps.width === nextProps.width &&
    prevProps.height === nextProps.height
  );
});
