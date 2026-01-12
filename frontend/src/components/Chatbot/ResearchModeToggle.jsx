import { Box, Switch, Typography, Tooltip } from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';

/**
 * Toggle switch for enabling Deep Research mode.
 * When enabled, the chatbot performs multi-step research with parallel units.
 */
function ResearchModeToggle({ researchMode, onToggle, disabled = false }) {
  return (
    <Tooltip
      title={
        researchMode
          ? "Deep Research: Multi-step analysis with parallel research units"
          : "Enable Deep Research for comprehensive analysis"
      }
      arrow
      placement="top"
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          px: 1,
          py: 0.5,
          borderRadius: 1,
          backgroundColor: researchMode ? 'primary.50' : 'transparent',
          border: researchMode ? '1px solid' : '1px solid transparent',
          borderColor: researchMode ? 'primary.200' : 'transparent',
          transition: 'all 0.2s ease',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
          '&:hover': {
            backgroundColor: disabled ? undefined : (researchMode ? 'primary.100' : 'action.hover'),
          },
        }}
        onClick={() => !disabled && onToggle(!researchMode)}
      >
        <ScienceIcon
          fontSize="small"
          sx={{
            color: researchMode ? 'primary.main' : 'text.secondary',
            fontSize: '1.1rem',
          }}
        />
        <Switch
          size="small"
          checked={researchMode}
          onChange={(e) => onToggle(e.target.checked)}
          disabled={disabled}
          sx={{
            '& .MuiSwitch-switchBase.Mui-checked': {
              color: 'primary.main',
            },
            '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
              backgroundColor: 'primary.main',
            },
          }}
        />
        <Typography
          variant="caption"
          sx={{
            color: researchMode ? 'primary.main' : 'text.secondary',
            fontWeight: researchMode ? 600 : 400,
            userSelect: 'none',
          }}
        >
          Deep
        </Typography>
      </Box>
    </Tooltip>
  );
}

export default ResearchModeToggle;
