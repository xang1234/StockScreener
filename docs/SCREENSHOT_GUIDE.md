# Screenshot & GIF Capture Guide

This guide provides detailed instructions for capturing screenshots and GIFs for the README.

## Tools Recommended

### Screenshots
- **macOS**: Built-in Screenshot (Cmd+Shift+4) or CleanShot X
- **Windows**: Snipping Tool or ShareX
- **Cross-platform**: Browser DevTools (F12 → Device toolbar for consistent sizing)

### GIFs
- **macOS**: Kap (free), CleanShot X, or LICEcap
- **Windows**: ScreenToGif or LICEcap
- **Cross-platform**: Gifski (for converting video to GIF)

## Recommended Settings

- **Browser width**: 1400px (shows full UI without excessive whitespace)
- **Screenshot format**: PNG (lossless, good for UI)
- **GIF settings**: 15-20 FPS, max 10 seconds, optimize for web
- **Theme**: Dark mode (default) - provides better contrast for README

## Screenshots to Capture

### 1. scan-results.png
**Location**: `/scan` page
**What to capture**: Full scan results table showing:
- Screener selection chips at top (Min, CAN, IPO, etc.)
- Results table with 15-20 rows of data
- Visible columns: Ticker, Name, Composite Score, RS Rating, Stage, Price, screener scores
- RS sparklines and price change sparklines visible
- Sort by Composite Score descending

**Setup**:
1. Run a scan with all screeners enabled on "All Stocks" universe
2. Wait for completion
3. Ensure table shows good variety (high scores, Stage 2 stocks)
4. Capture the main results area

---

### 2. scan-filters.png
**Location**: `/scan` page
**What to capture**: Expanded filter panel showing:
- Multiple filter categories visible (Fundamental, Technical, Rating)
- Some active filters applied (RS > 70, Stage = 2)
- Filter preset dropdown visible if possible

**Setup**:
1. Expand the filter panel
2. Set a few representative filters
3. Capture the filter panel area

---

### 3. watchlist-table.png
**Location**: `/` (home page) → Watchlists tab
**What to capture**: Watchlist table showing:
- 8-12 stocks with data
- RS sparklines (small line charts)
- Price sparklines
- Price change bars (green/red horizontal bars)
- Watchlist selector dropdown visible

**Setup**:
1. Navigate to home page, click Watchlists tab
2. Select a watchlist with diverse stocks
3. Ensure price change bars show both gains and losses
4. Capture the table area

---

### 4. breadth-chart.png
**Location**: `/breadth` page
**What to capture**: Full breadth page showing:
- Main chart with breadth areas (green/red stacked)
- SPY price line overlay
- Time range selector (3M or 6M selected)
- Right panel with current breadth data
- Daily movers section

**Setup**:
1. Navigate to Market Breadth page
2. Select 3M or 6M time range
3. Ensure chart shows interesting breadth patterns
4. Capture the full page or chart + right panel

---

### 5. group-rankings.png
**Location**: `/groups` page
**What to capture**: Group rankings layout showing:
- Left panel: Top movers (gainers/losers cards)
- Right panel: Full rankings table
- Color-coded rank badges (green for top 20, red for bottom 20)
- Rank change arrows visible

**Setup**:
1. Navigate to Group Rankings page
2. Ensure movers panel shows meaningful changes
3. Scroll table to show top-ranked groups
4. Capture the full page layout

---

### 6. group-detail.png
**Location**: `/groups` page → Click any group row
**What to capture**: Group detail modal showing:
- Group name and current rank
- Rank history line chart
- Rank change cards (1W/1M/3M/6M)
- Constituent stocks table (partial)

**Setup**:
1. Click on an interesting group (one with rank changes)
2. Ensure chart shows rank movement over time
3. Capture the modal (may need to resize)

---

### 7. chatbot.png
**Location**: `/chatbot` page
**What to capture**: Chatbot interface showing:
- Left sidebar with conversation list/folders
- Main chat area with a few message exchanges
- Model selector or settings visible
- Research mode toggle if possible

**Setup**:
1. Navigate to Chatbot page
2. Have an existing conversation with stock research (e.g., "Analyze NVDA")
3. Show both user and assistant messages
4. Capture the full page

---

### 8. themes.png
**Location**: `/themes` page
**What to capture**: Themes page showing:
- Theme rankings table with momentum scores
- Emerging themes panel (right side)
- Alerts section if populated
- Source filter chips (Substack, Twitter, etc.)

**Setup**:
1. Navigate to Themes page
2. Ensure themes are populated with data
3. Select Technical or Fundamental pipeline
4. Capture the main content area

---

### 9. signals.png
**Location**: `/signals` page
**What to capture**: Signals page showing:
- Left panel: Stock table with signal counts
- Center: Price chart with signal markers overlaid
- Right/bottom: Detector panels
- Control panel with detector selection

**Setup**:
1. Navigate to Signals page
2. Run signal detection or view existing signals
3. Select a stock with detected signals
4. Ensure chart shows signal markers
5. Capture the full page layout

---

## GIFs to Capture

### 1. scan-workflow.gif (Hero GIF)
**Duration**: 8-10 seconds
**What to capture**: Complete scan workflow:
1. Start on `/scan` page with no results
2. Select screeners (click Min, CAN chips)
3. Click "Start Scan" button
4. Show progress bar filling
5. Results populating in table
6. Optional: Quick scroll through results

**Tips**:
- Use "Test" universe (20 stocks) for faster demo
- Optimize GIF size (target < 5MB)
- Ensure smooth scrolling

---

### 2. chart-interaction.gif (Optional)
**Duration**: 5-7 seconds
**What to capture**: Chart modal interaction:
1. Click chart icon on a stock row
2. Chart modal opens with candlestick chart
3. Hover over chart showing tooltip
4. Close modal

---

## File Checklist

After capturing, verify you have:

```
docs/
├── screenshots/
│   ├── scan-results.png      ← Multi-screener results table
│   ├── scan-filters.png      ← Filter panel expanded
│   ├── watchlist-table.png   ← Watchlist with sparklines
│   ├── breadth-chart.png     ← Breadth chart with SPY overlay
│   ├── group-rankings.png    ← IBD group rankings page
│   ├── group-detail.png      ← Group detail modal
│   ├── chatbot.png           ← AI chatbot interface
│   ├── themes.png            ← Theme discovery page
│   └── signals.png           ← Signal detection page
└── gifs/
    └── scan-workflow.gif     ← Hero GIF of scan process
```

## Image Optimization

Before committing, optimize images for web:

```bash
# Install optipng and gifsicle (macOS)
brew install optipng gifsicle

# Optimize PNGs
optipng -o5 docs/screenshots/*.png

# Optimize GIFs
gifsicle -O3 --colors 256 docs/gifs/*.gif -o docs/gifs/*.gif
```

Or use online tools:
- PNGs: TinyPNG (https://tinypng.com)
- GIFs: ezgif.com optimizer

## Tips for Great Screenshots

1. **Consistent sizing**: Use same browser width for all captures
2. **Clean data**: Use realistic but not sensitive stock data
3. **Visual variety**: Show green and red values, different stages
4. **No personal info**: Avoid capturing any API keys or personal data
5. **Dark mode**: Looks better on GitHub's default view
6. **Crop tightly**: Remove browser chrome, focus on the UI

## Updating Screenshots

When the UI changes significantly:
1. Re-capture affected screenshots
2. Optimize the new images
3. Commit with message: `docs: update screenshots for [feature] changes`
