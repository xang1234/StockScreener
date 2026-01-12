/**
 * TickerInputDialog - Dialog for entering a ticker when using a prompt with {ticker} placeholder.
 */
import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  Paper,
} from '@mui/material';

function TickerInputDialog({ open, onClose, onInsert, promptContent, promptName }) {
  const [ticker, setTicker] = useState('');

  // Reset ticker when dialog opens
  useEffect(() => {
    if (open) {
      setTicker('');
    }
  }, [open]);

  // Replace all {ticker} placeholders (case-insensitive)
  const getPreviewContent = () => {
    if (!ticker.trim()) {
      return promptContent;
    }
    return promptContent.replace(/\{ticker\}/gi, ticker.trim().toUpperCase());
  };

  const handleInsert = () => {
    if (!ticker.trim()) return;
    onInsert(getPreviewContent());
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleInsert();
    }
  };

  const previewContent = getPreviewContent();
  const hasTicker = ticker.trim().length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { maxHeight: '80vh' },
      }}
    >
      <DialogTitle>
        Enter Ticker - {promptName}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label="Stock Ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="e.g., AAPL, TSLA, NVDA"
            fullWidth
            size="small"
            autoFocus
            inputProps={{
              style: { textTransform: 'uppercase' },
              maxLength: 10,
            }}
          />

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
              Preview:
            </Typography>
            <Paper
              variant="outlined"
              sx={{
                p: 1.5,
                maxHeight: 200,
                overflow: 'auto',
                backgroundColor: 'action.hover',
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontFamily: 'inherit',
                }}
              >
                {previewContent}
              </Typography>
            </Paper>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={handleInsert}
          variant="contained"
          disabled={!hasTicker}
        >
          Insert Prompt
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default TickerInputDialog;
