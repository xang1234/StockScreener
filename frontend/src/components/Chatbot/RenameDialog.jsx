/**
 * RenameDialog - Simple dialog for renaming conversations or folders.
 */
import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Alert,
} from '@mui/material';

/**
 * Dialog for renaming a chat or folder.
 *
 * @param {Object} props
 * @param {boolean} props.open - Whether dialog is open
 * @param {Function} props.onClose - Callback when dialog closes
 * @param {Function} props.onSave - Callback when save is clicked (receives new name)
 * @param {string} props.title - Dialog title
 * @param {string} props.initialName - Current name
 * @param {string} props.label - Text field label
 * @param {string} props.placeholder - Text field placeholder
 * @param {string|null} props.error - Error message to display
 * @param {boolean} props.isLoading - Whether save is in progress
 * @param {number} props.maxLength - Maximum name length (default: 200)
 */
function RenameDialog({
  open,
  onClose,
  onSave,
  title = 'Rename',
  initialName = '',
  label = 'Name',
  placeholder = 'Enter name',
  error = null,
  isLoading = false,
  maxLength = 200,
}) {
  const [name, setName] = useState(initialName);

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setName(initialName);
    }
  }, [open, initialName]);

  const handleSave = () => {
    const trimmedName = name.trim();
    if (trimmedName && trimmedName !== initialName) {
      onSave(trimmedName);
    } else if (trimmedName === initialName) {
      onClose();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && name.trim() && !isLoading) {
      handleSave();
    }
    if (e.key === 'Escape') {
      onClose();
    }
  };

  const isUnchanged = name.trim() === initialName;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{ sx: { borderRadius: 2 } }}
    >
      <DialogTitle sx={{ pb: 1 }}>{title}</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <TextField
          autoFocus
          label={label}
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          size="small"
          sx={{ mt: 1 }}
          inputProps={{ maxLength }}
          disabled={isLoading}
        />
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          disabled={!name.trim() || isLoading || isUnchanged}
        >
          {isLoading ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default RenameDialog;
