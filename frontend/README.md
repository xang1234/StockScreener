# Stock Scanner - CANSLIM + Minervini

Comprehensive stock scanner using CANSLIM (William O'Neil) and Minervini methods to find high-quality stocks with relative strength, combined with industry group leadership analysis and Twitter sentiment.

## Overview

This scanner identifies stocks with strong fundamentals, technical setups, and momentum by implementing:

- **CANSLIM Criteria**: Current earnings, Annual earnings, New highs, Supply/Demand, Leader/Laggard, Institutional sponsorship, Market direction
- **Minervini Template**: Relative strength > 70, Stage 2 uptrend, Moving average alignment, VCP patterns
- **Industry Group Analysis**: Track sector/industry leadership and trending groups
- **Twitter Sentiment** (optional): Social media sentiment analysis when API credentials available

## Technology Stack

### Backend (Python)
- FastAPI for REST API
- SQLAlchemy + SQLite for data caching
- yfinance for price/volume data
- Alpha Vantage for fundamental data
- Custom rate limiting and caching

### Frontend (React)
- React + Vite
- Material-UI or shadcn/ui
- Recharts for charting
- TanStack Table for results
- React Query for state management

## Current Status

**Phase 1: Foundation & Setup** ✅ **COMPLETED**
- ✅ Backend FastAPI project structure
- ✅ SQLite database with SQLAlchemy models
- ✅ Database schema (12 tables)
- ✅ yfinance service wrapper
- ✅ Alpha Vantage service wrapper
- ✅ Rate limiter utility
- ✅ Caching service
- ✅ Stock data API endpoints
- 🔄 Frontend initialization (in progress)

## Quick Start

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add Alpha Vantage API key (optional)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for API documentation

### Frontend (coming soon)

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `GET /api/v1/stocks/{symbol}/info` - Basic stock info
- `GET /api/v1/stocks/{symbol}/fundamentals` - Fundamental data
- `GET /api/v1/stocks/{symbol}/technicals` - Technical indicators
- `GET /api/v1/stocks/{symbol}` - Complete stock data
- `GET /api/v1/stocks/{symbol}/industry` - Industry classification

## Stock Universe

- **Full NYSE**: All NYSE-listed stocks (~2,500 stocks)
- **Full NASDAQ**: All NASDAQ-listed stocks (~3,500 stocks)
- **Total Universe**: ~6,000 stocks
- **Industry Classification**: GICS sectors and industries (11 sectors, 69+ industries)

## Implementation Phases

- [x] **Phase 1**: Foundation & Setup
- [ ] **Phase 2**: Technical Analysis (Minervini Criteria)
- [ ] **Phase 3**: Fundamental Analysis (CANSLIM Criteria)
- [ ] **Phase 4**: Volume, Price Action & Market Analysis
- [ ] **Phase 5**: Stock Universe & Bulk Scanning
- [ ] **Phase 6**: Scoring System & Results
- [ ] **Phase 7**: Industry Group Analysis
- [ ] **Phase 8**: Watchlist & User Features
- [ ] **Phase 9**: Optimization & Polish
- [ ] **Phase 10**: Twitter Integration (Future)

## Database Schema

**Core Tables:**
- `stock_prices` - Historical OHLCV data
- `stock_fundamentals` - EPS, revenue, institutional data
- `stock_technicals` - MA values, RS rating, stage, VCP score
- `scan_results` - Individual stock scores from scans
- `scans` - Scan metadata and configuration
- `watchlist` - User-tracked stocks
- `market_status` - Daily market trend data

**Industry Analysis Tables:**
- `industries` - Industry/sector master list (GICS)
- `stock_industry` - Stock-to-industry mapping
- `industry_performance` - Group RS ratings and leadership scores
- `sector_rotation` - Historical sector rotation data

## Features (Planned)

### CANSLIM Scoring
- Current quarterly EPS growth > 25%
- Annual EPS growth > 25% for 3 years
- Price within 15% of 52-week high
- Volume increasing on up days
- Relative strength > 70
- Institutional ownership 40-70%, increasing
- Market in confirmed uptrend

### Minervini Template
- Relative Strength Rating > 80
- Stage 2 uptrend (Weinstein Stage Analysis)
- Price > 50-day > 150-day > 200-day MA
- 200-day MA trending up for 1+ month
- Price 30%+ above 52-week low, within 25% of high
- Volatility Contraction Pattern (VCP) detection

### Industry Group Leadership
- Group relative strength calculation
- Leadership scoring (Stage 2 %, high-RS stocks)
- Trending groups detection (RS > 70, improving)
- Sector rotation analysis (4-quadrant model)
- Industry filtering for scans

## Rate Limits & Caching

- **yfinance**: 1 req/sec (self-imposed)
- **Alpha Vantage Free**: 25 req/day
  - Fundamentals cached for 7 days
  - Technicals cached for 24 hours
  - Smart batching and prioritization

## Documentation

- Backend API: See `backend/README.md`
- Frontend: See `frontend/README.md` (coming soon)
- Implementation Plan: See `.claude/plans/async-shimmying-rossum.md`

## Contributing

This is a personal project following CANSLIM and Minervini methodologies for stock screening.

## License

MIT

## Disclaimer

This software is for educational and research purposes only. It is not financial advice. Always do your own research and consult with a licensed financial advisor before making investment decisions.
