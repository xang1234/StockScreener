import { Box, ToggleButtonGroup, ToggleButton, Typography } from '@mui/material';

/**
 * Compact tri-state toggle for boolean filters
 * States: null (All), true (Yes), false (No)
 */
function CompactCheckbox({ label, value, onChange }) {
  const handleChange = (event, newValue) => {
    // If clicking same button, reset to null (All)
    if (newValue === null && value !== null) {
      onChange(null);
    } else {
      onChange(newValue);
    }
  };

  return (
    <Box sx={{ minWidth: 60 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mb: 0.5, fontSize: '0.7rem' }}
      >
        {label}
      </Typography>
      <ToggleButtonGroup
        value={value}
        exclusive
        onChange={handleChange}
        size="small"
        sx={{
          height: 28,
          '& .MuiToggleButton-root': {
            padding: '2px 6px',
            fontSize: '0.65rem',
            textTransform: 'none',
            minWidth: 28,
          },
        }}
      >
        <ToggleButton value={null} aria-label="all">
          All
        </ToggleButton>
        <ToggleButton value={true} aria-label="yes" sx={{ color: 'success.main' }}>
          Yes
        </ToggleButton>
        <ToggleButton value={false} aria-label="no" sx={{ color: 'error.main' }}>
          No
        </ToggleButton>
      </ToggleButtonGroup>
    </Box>
  );
}

export default CompactCheckbox;
