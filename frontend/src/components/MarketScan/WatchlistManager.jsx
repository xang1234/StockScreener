/**
 * Watchlist management modal with drag-drop reordering.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Box,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import AddIcon from '@mui/icons-material/Add';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import {
  getWatchlist,
  addSymbol,
  removeSymbol,
  reorderSymbols,
} from '../../api/marketScan';

function WatchlistManager({ open, onClose, listName, onUpdate }) {
  const queryClient = useQueryClient();
  const [newSymbol, setNewSymbol] = useState('');
  const [error, setError] = useState('');

  // Fetch current watchlist
  const { data: watchlist, isLoading } = useQuery({
    queryKey: ['marketScan', listName],
    queryFn: () => getWatchlist(listName),
    enabled: open,
  });

  // Add symbol mutation
  const addMutation = useMutation({
    mutationFn: (symbolData) => addSymbol(listName, symbolData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketScan', listName] });
      setNewSymbol('');
      setError('');
      onUpdate?.();
    },
    onError: (err) => {
      setError(err.response?.data?.detail || 'Failed to add symbol');
    },
  });

  // Remove symbol mutation
  const removeMutation = useMutation({
    mutationFn: (symbolId) => removeSymbol(listName, symbolId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketScan', listName] });
      onUpdate?.();
    },
  });

  // Reorder mutation
  const reorderMutation = useMutation({
    mutationFn: (symbolIds) => reorderSymbols(listName, symbolIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketScan', listName] });
      onUpdate?.();
    },
  });

  const handleAddSymbol = () => {
    if (newSymbol.trim()) {
      setError('');
      addMutation.mutate({ symbol: newSymbol.trim().toUpperCase() });
    }
  };

  const handleDragEnd = (result) => {
    if (!result.destination || !watchlist?.symbols) return;
    moveItem(result.source.index, result.destination.index);
  };

  const moveItem = (fromIndex, toIndex) => {
    if (!watchlist?.symbols) return;
    if (toIndex < 0 || toIndex >= watchlist.symbols.length) return;

    const items = Array.from(watchlist.symbols);
    const [reorderedItem] = items.splice(fromIndex, 1);
    items.splice(toIndex, 0, reorderedItem);

    // Optimistically update the cache
    queryClient.setQueryData(['marketScan', listName], {
      ...watchlist,
      symbols: items,
    });

    // Send new order to backend
    const newOrder = items.map((item) => item.id);
    reorderMutation.mutate(newOrder);
  };

  const moveUp = (index) => moveItem(index, index - 1);
  const moveDown = (index) => moveItem(index, index + 1);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Manage Watchlist</DialogTitle>
      <DialogContent>
        {/* Add new symbol */}
        <Box display="flex" gap={1} mb={2} mt={1}>
          <TextField
            size="small"
            placeholder="Enter symbol (e.g., AAPL or TVC:VIX)"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleAddSymbol()}
            fullWidth
            disabled={addMutation.isPending}
          />
          <Button
            variant="contained"
            onClick={handleAddSymbol}
            disabled={addMutation.isPending || !newSymbol.trim()}
            startIcon={<AddIcon />}
          >
            Add
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
          Drag to reorder. Use TradingView format for special symbols (e.g., FX:USDSGD, BITSTAMP:BTCUSD, TVC:VIX)
        </Typography>

        {/* Symbol list with drag-drop */}
        {isLoading ? (
          <Box display="flex" justifyContent="center" p={3}>
            <CircularProgress />
          </Box>
        ) : (
          <DragDropContext onDragEnd={handleDragEnd}>
            <Droppable droppableId="symbols">
              {(provided) => (
                <List {...provided.droppableProps} ref={provided.innerRef} sx={{ minHeight: 100 }}>
                  {watchlist?.symbols?.map((symbol, index) => (
                    <Draggable
                      key={symbol.id}
                      draggableId={String(symbol.id)}
                      index={index}
                    >
                      {(provided, snapshot) => (
                        <ListItem
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          sx={{
                            bgcolor: snapshot.isDragging ? 'action.hover' : 'transparent',
                            borderRadius: 1,
                            mb: 0.5,
                            border: '1px solid',
                            borderColor: snapshot.isDragging ? 'primary.main' : 'divider',
                          }}
                          secondaryAction={
                            <Box display="flex" alignItems="center" gap={0.5}>
                              <IconButton
                                size="small"
                                onClick={() => moveUp(index)}
                                disabled={index === 0 || reorderMutation.isPending}
                                title="Move up"
                              >
                                <KeyboardArrowUpIcon fontSize="small" />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={() => moveDown(index)}
                                disabled={index === watchlist.symbols.length - 1 || reorderMutation.isPending}
                                title="Move down"
                              >
                                <KeyboardArrowDownIcon fontSize="small" />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={() => removeMutation.mutate(symbol.id)}
                                disabled={removeMutation.isPending}
                                title="Delete"
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          }
                        >
                          <Box
                            {...provided.dragHandleProps}
                            sx={{ mr: 1, display: 'flex', alignItems: 'center', cursor: 'grab' }}
                          >
                            <DragIndicatorIcon color="action" />
                          </Box>
                          <ListItemText
                            primary={symbol.symbol}
                            secondary={symbol.display_name}
                            primaryTypographyProps={{ fontWeight: 600 }}
                          />
                        </ListItem>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                </List>
              )}
            </Droppable>
          </DragDropContext>
        )}

        {watchlist?.symbols?.length === 0 && (
          <Typography color="text.secondary" textAlign="center" py={3}>
            No symbols in watchlist. Add some above.
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default WatchlistManager;
