/**
 * FilterPresets component - compact UI for managing filter presets.
 * Displays a dropdown to select presets, save button, and update button.
 */
import { useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  Select,
  MenuItem,
  IconButton,
  Menu,
  ListItemIcon,
  ListItemText,
  Divider,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import SyncIcon from '@mui/icons-material/Sync';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

/**
 * FilterPresets component for managing saved filter configurations.
 *
 * @param {Object} props
 * @param {Array} props.presets - List of available presets
 * @param {number|null} props.activePresetId - Currently selected preset ID
 * @param {boolean} props.hasUnsavedChanges - Whether current filters differ from preset
 * @param {boolean} props.isLoading - Whether presets are loading
 * @param {boolean} props.isSaving - Whether a save operation is in progress
 * @param {Function} props.onLoadPreset - Callback when a preset is selected
 * @param {Function} props.onSavePreset - Callback to open save dialog
 * @param {Function} props.onUpdatePreset - Callback to update current preset
 * @param {Function} props.onRenamePreset - Callback to rename a preset
 * @param {Function} props.onDeletePreset - Callback to delete a preset
 */
function FilterPresets({
  presets = [],
  activePresetId,
  hasUnsavedChanges,
  isLoading,
  isSaving,
  onLoadPreset,
  onSavePreset,
  onUpdatePreset,
  onRenamePreset,
  onDeletePreset,
}) {
  const [menuAnchor, setMenuAnchor] = useState(null);

  const handleMenuOpen = (event) => {
    event.stopPropagation();
    setMenuAnchor(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
  };

  const handleRename = () => {
    handleMenuClose();
    if (activePresetId && onRenamePreset) {
      onRenamePreset(activePresetId);
    }
  };

  const handleDelete = () => {
    handleMenuClose();
    if (activePresetId && onDeletePreset) {
      const preset = presets.find(p => p.id === activePresetId);
      if (preset && window.confirm(`Delete preset "${preset.name}"?`)) {
        onDeletePreset(activePresetId);
      }
    }
  };

  const activePreset = presets.find(p => p.id === activePresetId);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
      {/* Preset Dropdown */}
      <FormControl size="small" sx={{ minWidth: 140 }}>
        <Select
          value={activePresetId || ''}
          onChange={(e) => onLoadPreset(e.target.value || null)}
          displayEmpty
          sx={{
            height: 28,
            fontSize: '0.75rem',
            '& .MuiSelect-select': { py: 0.5, pr: 3 },
          }}
          disabled={isLoading}
        >
          <MenuItem value="">
            <em style={{ color: '#999' }}>Select Preset</em>
          </MenuItem>
          {presets.map((preset) => (
            <MenuItem key={preset.id} value={preset.id}>
              {preset.name}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {/* Save Button */}
      <Tooltip title="Save as new preset">
        <span>
          <Button
            size="small"
            variant="outlined"
            onClick={onSavePreset}
            disabled={isSaving}
            sx={{
              minWidth: 32,
              height: 28,
              p: 0.5,
            }}
          >
            {isSaving ? (
              <CircularProgress size={14} />
            ) : (
              <SaveIcon sx={{ fontSize: 16 }} />
            )}
          </Button>
        </span>
      </Tooltip>

      {/* Update Button - only show when preset is loaded and has changes */}
      {activePresetId && hasUnsavedChanges && (
        <Tooltip title={`Update "${activePreset?.name || 'preset'}"`}>
          <span>
            <Button
              size="small"
              variant="contained"
              color="warning"
              onClick={onUpdatePreset}
              disabled={isSaving}
              sx={{
                minWidth: 32,
                height: 28,
                p: 0.5,
              }}
            >
              {isSaving ? (
                <CircularProgress size={14} color="inherit" />
              ) : (
                <SyncIcon sx={{ fontSize: 16 }} />
              )}
            </Button>
          </span>
        </Tooltip>
      )}

      {/* More Menu - only show when preset is selected */}
      {activePresetId && (
        <>
          <IconButton
            size="small"
            onClick={handleMenuOpen}
            sx={{ width: 28, height: 28 }}
          >
            <MoreVertIcon sx={{ fontSize: 16 }} />
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={handleMenuClose}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          >
            <MenuItem onClick={handleRename}>
              <ListItemIcon>
                <EditIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Rename</ListItemText>
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
              <ListItemIcon>
                <DeleteIcon fontSize="small" color="error" />
              </ListItemIcon>
              <ListItemText>Delete</ListItemText>
            </MenuItem>
          </Menu>
        </>
      )}
    </Box>
  );
}

export default FilterPresets;
