/**
 * SavePresetDialog component - MUI Dialog for saving/renaming filter presets.
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
 * Dialog for saving or renaming a filter preset.
 *
 * @param {Object} props
 * @param {boolean} props.open - Whether dialog is open
 * @param {Function} props.onClose - Callback when dialog closes
 * @param {Function} props.onSave - Callback when save is clicked (receives name and description)
 * @param {string} props.mode - 'save' for new preset, 'rename' for existing
 * @param {string} props.initialName - Initial preset name (for rename mode)
 * @param {string} props.initialDescription - Initial description (for rename mode)
 * @param {string|null} props.error - Error message to display
 * @param {boolean} props.isLoading - Whether save is in progress
 */
function SavePresetDialog({
  open,
  onClose,
  onSave,
  mode = 'save',
  initialName = '',
  initialDescription = '',
  error = null,
  isLoading = false,
}) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setName(initialName);
      setDescription(initialDescription);
    }
  }, [open, initialName, initialDescription]);

  const handleSave = () => {
    if (name.trim()) {
      onSave(name.trim(), description.trim());
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && name.trim() && !isLoading) {
      handleSave();
    }
  };

  const title = mode === 'rename' ? 'Rename Preset' : 'Save Filter Preset';
  const saveButtonText = mode === 'rename' ? 'Rename' : 'Save';

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
          label="Preset Name"
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g., High RS Leaders"
          size="small"
          sx={{ mt: 1, mb: 2 }}
          inputProps={{ maxLength: 100 }}
          disabled={isLoading}
        />
        <TextField
          label="Description (optional)"
          fullWidth
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g., RS > 80, Stage 2"
          size="small"
          multiline
          rows={2}
          inputProps={{ maxLength: 500 }}
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
          disabled={!name.trim() || isLoading}
        >
          {isLoading ? 'Saving...' : saveButtonText}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default SavePresetDialog;
