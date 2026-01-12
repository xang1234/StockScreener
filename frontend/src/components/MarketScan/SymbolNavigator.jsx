/**
 * Symbol navigation controls with prev/next buttons and symbol menu.
 */
import { useState } from 'react';
import { Box, IconButton, Typography, Menu, MenuItem } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

function SymbolNavigator({
  currentIndex,
  total,
  onPrevious,
  onNext,
  onSelectIndex,
  symbols,
}) {
  const [anchorEl, setAnchorEl] = useState(null);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleSelect = (index) => {
    onSelectIndex(index);
    handleClose();
  };

  return (
    <Box display="flex" alignItems="center" gap={0.5}>
      <IconButton onClick={onPrevious} size="small" title="Previous (Shift+Space)">
        <ChevronLeftIcon />
      </IconButton>

      <Typography
        variant="body2"
        sx={{
          cursor: 'pointer',
          px: 1,
          py: 0.5,
          borderRadius: 1,
          minWidth: 50,
          textAlign: 'center',
          '&:hover': { bgcolor: 'action.hover' },
        }}
        onClick={handleClick}
        title="Click to jump to symbol"
      >
        {currentIndex + 1} / {total}
      </Typography>

      <IconButton onClick={onNext} size="small" title="Next (Space)">
        <ChevronRightIcon />
      </IconButton>

      {/* Symbol selection menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        {symbols.map((sym, idx) => (
          <MenuItem
            key={sym.id}
            onClick={() => handleSelect(idx)}
            selected={idx === currentIndex}
          >
            {sym.display_name || sym.symbol}
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}

export default SymbolNavigator;
