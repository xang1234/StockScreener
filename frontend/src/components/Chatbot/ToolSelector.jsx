/**
 * ToolSelector - Hierarchical popover for selecting chatbot tools.
 */
import { useState } from 'react';
import {
  Box,
  IconButton,
  Popover,
  Typography,
  Button,
  Checkbox,
  Collapse,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Badge,
} from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import StorageIcon from '@mui/icons-material/Storage';
import LanguageIcon from '@mui/icons-material/Language';
import DescriptionIcon from '@mui/icons-material/Description';

import { TOOL_CATEGORIES } from '../../config/chatbotTools';

// Map icon names to components
const ICON_MAP = {
  ShowChart: ShowChartIcon,
  Storage: StorageIcon,
  Language: LanguageIcon,
  Description: DescriptionIcon,
};

/**
 * Category row with checkbox and expand/collapse.
 */
function CategoryRow({ category, enabledTools, onToggleCategory, expanded, onToggleExpand }) {
  const toolNames = category.tools.map((t) => t.name);
  const enabledInCategory = toolNames.filter((name) => enabledTools.has(name)).length;
  const total = toolNames.length;

  // Checkbox state: checked (all), indeterminate (some), unchecked (none)
  const allEnabled = enabledInCategory === total;
  const someEnabled = enabledInCategory > 0 && enabledInCategory < total;

  const IconComponent = ICON_MAP[category.icon] || ShowChartIcon;

  return (
    <ListItemButton
      onClick={onToggleExpand}
      sx={{ py: 0.5 }}
    >
      <ListItemIcon sx={{ minWidth: 36 }}>
        <Checkbox
          edge="start"
          checked={allEnabled}
          indeterminate={someEnabled}
          onChange={(e) => {
            e.stopPropagation();
            onToggleCategory(toolNames);
          }}
          onClick={(e) => e.stopPropagation()}
          sx={{
            color: category.color,
            '&.Mui-checked': { color: category.color },
            '&.MuiCheckbox-indeterminate': { color: category.color },
          }}
        />
      </ListItemIcon>
      <ListItemIcon sx={{ minWidth: 32 }}>
        <IconComponent sx={{ fontSize: 20, color: category.color }} />
      </ListItemIcon>
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" fontWeight={500}>
              {category.label}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ({enabledInCategory}/{total})
            </Typography>
          </Box>
        }
      />
      {expanded ? <ExpandLess /> : <ExpandMore />}
    </ListItemButton>
  );
}

/**
 * Individual tool checkbox row.
 */
function ToolRow({ tool, enabled, onToggle, categoryColor }) {
  return (
    <ListItem sx={{ py: 0, pl: 8 }}>
      <ListItemIcon sx={{ minWidth: 36 }}>
        <Checkbox
          edge="start"
          checked={enabled}
          onChange={() => onToggle(tool.name)}
          size="small"
          sx={{
            color: categoryColor,
            '&.Mui-checked': { color: categoryColor },
          }}
        />
      </ListItemIcon>
      <ListItemText
        primary={
          <Typography variant="body2" color="text.secondary">
            {tool.label}
          </Typography>
        }
      />
    </ListItem>
  );
}

/**
 * ToolSelector component - displays a button that opens a popover with tool categories.
 */
function ToolSelector({
  enabledTools,
  toggleTool,
  toggleCategory,
  enableAll,
  disableAll,
  enabledCount,
  totalCount,
  allEnabled,
}) {
  const [anchorEl, setAnchorEl] = useState(null);
  const [expandedCategories, setExpandedCategories] = useState({});

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleToggleExpand = (categoryId) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [categoryId]: !prev[categoryId],
    }));
  };

  const open = Boolean(anchorEl);

  return (
    <>
      <Badge
        badgeContent={allEnabled ? 0 : enabledCount}
        color="primary"
        max={99}
        sx={{
          '& .MuiBadge-badge': {
            fontSize: '0.65rem',
            height: 16,
            minWidth: 16,
          },
        }}
      >
        <IconButton
          onClick={handleClick}
          size="small"
          sx={{
            color: allEnabled ? 'text.secondary' : 'primary.main',
            backgroundColor: open ? 'action.selected' : 'transparent',
            '&:hover': {
              backgroundColor: 'action.hover',
            },
          }}
          title="Select Tools"
        >
          <TuneIcon />
        </IconButton>
      </Badge>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        slotProps={{
          paper: {
            sx: {
              width: 300,
              maxHeight: 450,
            },
          },
        }}
      >
        {/* Header */}
        <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Select Tools
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {enabledCount} of {totalCount} tools enabled
          </Typography>
        </Box>

        {/* Action buttons */}
        <Box
          sx={{
            px: 2,
            py: 1,
            display: 'flex',
            gap: 1,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Button
            size="small"
            variant="text"
            onClick={enableAll}
            disabled={allEnabled}
            sx={{ textTransform: 'none', fontSize: '0.75rem' }}
          >
            Select All
          </Button>
          <Button
            size="small"
            variant="text"
            onClick={disableAll}
            disabled={enabledCount === 0}
            sx={{ textTransform: 'none', fontSize: '0.75rem' }}
          >
            Select None
          </Button>
        </Box>

        {/* Category list */}
        <List dense sx={{ py: 0, maxHeight: 320, overflowY: 'auto' }}>
          {Object.values(TOOL_CATEGORIES).map((category) => (
            <Box key={category.id}>
              <CategoryRow
                category={category}
                enabledTools={enabledTools}
                onToggleCategory={toggleCategory}
                expanded={expandedCategories[category.id] || false}
                onToggleExpand={() => handleToggleExpand(category.id)}
              />
              <Collapse
                in={expandedCategories[category.id] || false}
                timeout="auto"
                unmountOnExit
              >
                <List component="div" disablePadding dense>
                  {category.tools.map((tool) => (
                    <ToolRow
                      key={tool.name}
                      tool={tool}
                      enabled={enabledTools.has(tool.name)}
                      onToggle={toggleTool}
                      categoryColor={category.color}
                    />
                  ))}
                </List>
              </Collapse>
              <Divider />
            </Box>
          ))}
        </List>
      </Popover>
    </>
  );
}

export default ToolSelector;
