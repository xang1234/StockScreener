"""Adapter wrapping DataPreparationLayer as a StockDataProvider port."""

from __future__ import annotations

from app.domain.scanning.ports import StockDataProvider
from app.scanners.data_preparation import DataPreparationLayer


class DataPrepStockDataProvider(StockDataProvider):
    """Delegates to the existing DataPreparationLayer."""

    def __init__(self) -> None:
        self._layer = DataPreparationLayer()

    def prepare_data(self, symbol: str, requirements: object) -> object:
        return self._layer.prepare_data(symbol, requirements)

    def prepare_data_bulk(
        self, symbols: list[str], requirements: object
    ) -> dict[str, object]:
        return self._layer.prepare_data_bulk(symbols, requirements)
