/**
 * Tab component that embeds the Stockbee MM page in an iframe.
 */
import { Box } from '@mui/material';

function StockbeeMmTab() {
  return (
    <Box sx={{ height: '100%', width: '100%' }}>
      <iframe
        src="https://stockbee.blogspot.com/p/mm.html"
        style={{ width: '100%', height: '100%', border: 'none' }}
        title="Stockbee MM"
      />
    </Box>
  );
}

export default StockbeeMmTab;
