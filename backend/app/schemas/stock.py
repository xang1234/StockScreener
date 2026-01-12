"""Stock data schemas"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StockInfo(BaseModel):
    """Basic stock information"""
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[float] = None
    market_cap: Optional[int] = None


class StockFundamentals(BaseModel):
    """Stock fundamental data"""
    symbol: str
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    eps_current: Optional[float] = None
    eps_growth_quarterly: Optional[float] = None
    eps_growth_annual: Optional[float] = None
    revenue_current: Optional[int] = None
    revenue_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    institutional_ownership: Optional[float] = None
    description: Optional[str] = None


class StockTechnicals(BaseModel):
    """Stock technical indicators"""
    symbol: str
    current_price: Optional[float] = None
    ma_50: Optional[float] = None
    ma_150: Optional[float] = None
    ma_200: Optional[float] = None
    rs_rating: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    stage: Optional[int] = None
    vcp_score: Optional[float] = None


class StockData(BaseModel):
    """Complete stock data"""
    info: StockInfo
    fundamentals: Optional[StockFundamentals] = None
    technicals: Optional[StockTechnicals] = None
