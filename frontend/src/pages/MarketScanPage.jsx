/**
 * Market Scan page with vertical side tabs for different scan views.
 */
import { useState } from 'react';
import { Box, Tabs, Tab, Paper, Typography } from '@mui/material';
import KeyMarketsTab from '../components/MarketScan/KeyMarketsTab';
import ThemesTab from '../components/MarketScan/ThemesTab';
import WatchlistsTab from '../components/MarketScan/WatchlistsTab';
import StockbeeMmTab from '../components/MarketScan/StockbeeMmTab';

// Vertical tab panels - extensible for future sub-pages
const SUB_TABS = [
  { id: 'key_markets', label: 'Key Markets' },
  { id: 'themes', label: 'Themes' },
  { id: 'watchlists', label: 'Watchlists' },
  { id: 'stockbee_mm', label: 'Stockbee MM' },
];

function MarketScanPage() {
  const [selectedTab, setSelectedTab] = useState(0);

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 70px)' }}>
      {/* Left sidebar with vertical tabs */}
      <Paper
        elevation={1}
        sx={{
          width: 120,
          flexShrink: 0,
          borderRight: 1,
          borderColor: 'divider',
        }}
      >
        <Tabs
          orientation="vertical"
          value={selectedTab}
          onChange={(e, v) => setSelectedTab(v)}
          sx={{
            '& .MuiTab-root': {
              alignItems: 'flex-start',
              textAlign: 'left',
              minHeight: 36,
              px: 1.5,
              fontSize: '12px',
            },
          }}
        >
          {SUB_TABS.map((tab) => (
            <Tab
              key={tab.id}
              label={tab.label}
            />
          ))}
        </Tabs>
      </Paper>

      {/* Main content area */}
      <Box sx={{ flex: 1, overflow: 'hidden', p: 1 }}>
        {selectedTab === 0 && <KeyMarketsTab />}
        {selectedTab === 1 && <ThemesTab />}
        {selectedTab === 2 && <WatchlistsTab />}
        {selectedTab === 3 && <StockbeeMmTab />}
      </Box>
    </Box>
  );
}

export default MarketScanPage;
