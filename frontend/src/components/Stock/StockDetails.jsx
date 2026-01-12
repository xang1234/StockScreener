import { useParams } from 'react-router-dom';
import { Typography, Box } from '@mui/material';

function StockDetails() {
  const { symbol } = useParams();

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Stock Details: {symbol}
      </Typography>
      <Typography variant="body1">
        Detailed stock analysis coming in Phase 2+
      </Typography>
    </Box>
  );
}

export default StockDetails;
