"""Schemas for User-defined Themes"""
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


# ================= Theme Schemas =================

class UserThemeBase(BaseModel):
    """Base schema for a user theme"""
    name: str
    description: Optional[str] = None
    color: Optional[str] = None


class UserThemeCreate(UserThemeBase):
    """Schema for creating a new theme"""
    pass


class UserThemeUpdate(BaseModel):
    """Schema for updating a theme"""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None


class UserThemeResponse(UserThemeBase):
    """Response schema for a theme"""
    id: int
    position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ================= Subgroup Schemas =================

class SubgroupBase(BaseModel):
    """Base schema for a subgroup"""
    name: str


class SubgroupCreate(SubgroupBase):
    """Schema for creating a new subgroup"""
    pass


class SubgroupUpdate(BaseModel):
    """Schema for updating a subgroup"""
    name: Optional[str] = None
    position: Optional[int] = None
    is_collapsed: Optional[bool] = None


class SubgroupResponse(SubgroupBase):
    """Response schema for a subgroup"""
    id: int
    theme_id: int
    position: int
    is_collapsed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ================= Stock Schemas =================

class ThemeStockBase(BaseModel):
    """Base schema for a stock in a theme"""
    symbol: str
    display_name: Optional[str] = None
    notes: Optional[str] = None


class ThemeStockCreate(ThemeStockBase):
    """Schema for adding a stock to a subgroup"""
    pass


class ThemeStockUpdate(BaseModel):
    """Schema for updating a stock"""
    display_name: Optional[str] = None
    notes: Optional[str] = None
    position: Optional[int] = None
    subgroup_id: Optional[int] = None


class ThemeStockResponse(ThemeStockBase):
    """Response schema for a stock"""
    id: int
    subgroup_id: int
    position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ================= Stock Data Response (with sparklines/price changes) =================

class StockDataResponse(BaseModel):
    """Stock with computed market data for display in theme table"""
    id: int
    symbol: str
    display_name: Optional[str] = None
    subgroup_id: int
    position: int

    # Company info
    company_name: Optional[str] = None
    ibd_industry: Optional[str] = None

    # Sparkline data (30-day)
    rs_data: Optional[List[float]] = None
    rs_trend: Optional[int] = None
    price_data: Optional[List[float]] = None
    price_trend: Optional[int] = None

    # Price changes for bar chart (percentage)
    change_1d: Optional[float] = None
    change_5d: Optional[float] = None
    change_2w: Optional[float] = None
    change_1m: Optional[float] = None
    change_3m: Optional[float] = None
    change_6m: Optional[float] = None
    change_12m: Optional[float] = None


class SubgroupWithStocksResponse(BaseModel):
    """Subgroup with stocks and their market data"""
    id: int
    name: str
    position: int
    is_collapsed: bool
    stocks: List[StockDataResponse]


class PriceChangeBounds(BaseModel):
    """Min/max bounds for a price change period"""
    min: float
    max: float


class ThemeDataResponse(BaseModel):
    """Complete theme data for display"""
    id: int
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    subgroups: List[SubgroupWithStocksResponse]
    price_change_bounds: Dict[str, PriceChangeBounds]


class ThemeListResponse(BaseModel):
    """List of themes for toggle selector"""
    themes: List[UserThemeResponse]
    total: int


# ================= Reorder Schemas =================

class ReorderThemesRequest(BaseModel):
    """Request body for reordering themes"""
    theme_ids: List[int]


class ReorderSubgroupsRequest(BaseModel):
    """Request body for reordering subgroups"""
    subgroup_ids: List[int]


class ReorderStocksRequest(BaseModel):
    """Request body for reordering stocks"""
    stock_ids: List[int]
