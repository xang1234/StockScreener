import { Box, Chip, Typography } from '@mui/material';

/**
 * IPO Date filter with chip-based preset selector
 * Presets: 6M, 1Y, 2Y, 3Y, 5Y (meaning IPO'd within that time period)
 * Toggle behavior: click again to clear
 */
const IPO_PRESETS = [
  { value: '6m', label: '6M' },
  { value: '1y', label: '1Y' },
  { value: '2y', label: '2Y' },
  { value: '3y', label: '3Y' },
  { value: '5y', label: '5Y' },
];

function IpoDateFilter({ value, onChange }) {
  const handleChipClick = (presetValue) => {
    // Toggle behavior: click again to clear
    if (value === presetValue) {
      onChange(null);
    } else {
      onChange(presetValue);
    }
  };

  return (
    <Box sx={{ minWidth: 120 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mb: 0.5, fontSize: '0.7rem' }}
      >
        IPO Age
      </Typography>
      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
        {IPO_PRESETS.map((preset) => (
          <Chip
            key={preset.value}
            label={preset.label}
            size="small"
            variant={value === preset.value ? 'filled' : 'outlined'}
            color={value === preset.value ? 'primary' : 'default'}
            onClick={() => handleChipClick(preset.value)}
            sx={{
              height: 22,
              fontSize: '0.65rem',
              '& .MuiChip-label': { px: 0.75 },
            }}
          />
        ))}
      </Box>
    </Box>
  );
}

export default IpoDateFilter;
