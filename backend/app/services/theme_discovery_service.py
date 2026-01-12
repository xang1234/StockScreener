"""
Theme Discovery Service

Aggregates theme mentions, calculates metrics, and discovers emerging themes.
This is the intelligence layer that identifies what's trending.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from ..models.theme import (
    ThemeCluster,
    ThemeConstituent,
    ThemeMention,
    ThemeMetrics,
    ThemeAlert,
    ContentItem,
    ContentSource,
)
from ..models.stock import StockPrice
from ..models.scan_result import ScanResult

logger = logging.getLogger(__name__)


class ThemeDiscoveryService:
    """
    Service for discovering and ranking market themes

    Key capabilities:
    1. Calculate mention velocity (social signal strength)
    2. Calculate theme basket performance (price validation)
    3. Calculate internal correlation (cohesiveness)
    4. Rank themes by composite score
    5. Generate alerts for emerging themes
    """

    def __init__(self, db: Session, pipeline: str = "technical"):
        self.db = db
        self.pipeline = pipeline
        self.pipeline_config = None
        self._load_pipeline_config()

    def _load_pipeline_config(self):
        """Load pipeline-specific configuration for scoring weights and thresholds"""
        try:
            from ..config.pipeline_config import get_pipeline_config
            self.pipeline_config = get_pipeline_config(self.pipeline)
            logger.info(f"ThemeDiscoveryService loaded config for pipeline: {self.pipeline}")
        except Exception as e:
            logger.warning(f"Could not load pipeline config: {e}. Using default weights.")
            self.pipeline_config = None

    def calculate_mention_metrics(self, theme_cluster_id: int, as_of_date: Optional[datetime] = None) -> dict:
        """
        Calculate mention velocity and sentiment for a theme

        Returns:
            mentions_1d: mentions in last 1 day
            mentions_7d: mentions in last 7 days
            mentions_30d: mentions in last 30 days
            mention_velocity: 7d/30d ratio (>1 = accelerating)
            sentiment_score: weighted average sentiment (-1 to 1)
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        date_1d = as_of_date - timedelta(days=1)
        date_7d = as_of_date - timedelta(days=7)
        date_30d = as_of_date - timedelta(days=30)

        # Count mentions by time period (only from active sources)
        mentions_1d = self.db.query(func.count(ThemeMention.id)).join(
            ContentItem, ThemeMention.content_item_id == ContentItem.id
        ).join(
            ContentSource, ContentItem.source_id == ContentSource.id
        ).filter(
            ThemeMention.theme_cluster_id == theme_cluster_id,
            ThemeMention.mentioned_at >= date_1d,
            ThemeMention.mentioned_at <= as_of_date,
            ContentSource.is_active == True,
        ).scalar() or 0

        mentions_7d = self.db.query(func.count(ThemeMention.id)).join(
            ContentItem, ThemeMention.content_item_id == ContentItem.id
        ).join(
            ContentSource, ContentItem.source_id == ContentSource.id
        ).filter(
            ThemeMention.theme_cluster_id == theme_cluster_id,
            ThemeMention.mentioned_at >= date_7d,
            ThemeMention.mentioned_at <= as_of_date,
            ContentSource.is_active == True,
        ).scalar() or 0

        mentions_30d = self.db.query(func.count(ThemeMention.id)).join(
            ContentItem, ThemeMention.content_item_id == ContentItem.id
        ).join(
            ContentSource, ContentItem.source_id == ContentSource.id
        ).filter(
            ThemeMention.theme_cluster_id == theme_cluster_id,
            ThemeMention.mentioned_at >= date_30d,
            ThemeMention.mentioned_at <= as_of_date,
            ContentSource.is_active == True,
        ).scalar() or 0

        # Calculate velocity (7d vs 30d weekly average)
        # Compares last 7 days to the average week in the 30-day period
        if mentions_30d > 0:
            # If 7d mentions == 30d mentions, all activity is recent (new theme)
            # In this case, velocity = 1.0 (neutral) since we can't determine trend
            if mentions_7d == mentions_30d:
                mention_velocity = 1.0
            else:
                weekly_avg_30d = mentions_30d / 4.3  # ~4.3 weeks in 30 days
                raw_velocity = mentions_7d / weekly_avg_30d if weekly_avg_30d > 0 else 0
                # Cap velocity between 0.1 and 3.0 for display purposes
                mention_velocity = max(0.1, min(3.0, raw_velocity))
        else:
            mention_velocity = 1.0 if mentions_7d > 0 else 0

        # Calculate sentiment score (only from active sources)
        mentions = self.db.query(ThemeMention).join(
            ContentItem, ThemeMention.content_item_id == ContentItem.id
        ).join(
            ContentSource, ContentItem.source_id == ContentSource.id
        ).filter(
            ThemeMention.theme_cluster_id == theme_cluster_id,
            ThemeMention.mentioned_at >= date_30d,
            ThemeMention.mentioned_at <= as_of_date,
            ContentSource.is_active == True,
        ).all()

        sentiment_scores = []
        for m in mentions:
            if m.sentiment == "bullish":
                sentiment_scores.append(1.0 * m.confidence)
            elif m.sentiment == "bearish":
                sentiment_scores.append(-1.0 * m.confidence)
            else:
                sentiment_scores.append(0.0)

        sentiment_score = np.mean(sentiment_scores) if sentiment_scores else 0.0

        return {
            "mentions_1d": mentions_1d,
            "mentions_7d": mentions_7d,
            "mentions_30d": mentions_30d,
            "mention_velocity": round(mention_velocity, 2),
            "sentiment_score": round(sentiment_score, 3),
        }

    def calculate_price_metrics(self, theme_cluster_id: int, as_of_date: Optional[datetime] = None) -> dict:
        """
        Calculate price-based metrics for theme basket

        Returns:
            basket_return_1d, 1w, 1m: Equal-weight basket returns
            basket_rs_vs_spy: Relative strength vs SPY
            pct_above_50ma, pct_above_200ma: Breadth metrics
            pct_positive_1w: % of stocks up on week
            avg_internal_correlation: Average pairwise correlation
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        # Get theme constituents
        constituents = self.db.query(ThemeConstituent).filter(
            ThemeConstituent.theme_cluster_id == theme_cluster_id,
            ThemeConstituent.is_active == True,
        ).all()

        if not constituents:
            return self._empty_price_metrics()

        symbols = [c.symbol for c in constituents]

        # Fetch price data for constituents
        date_lookback = as_of_date - timedelta(days=60)  # Need 60 days for calculations

        prices_query = self.db.query(StockPrice).filter(
            StockPrice.symbol.in_(symbols),
            StockPrice.date >= date_lookback.date(),
            StockPrice.date <= as_of_date.date(),
        ).all()

        if not prices_query:
            return self._empty_price_metrics()

        # Convert to DataFrame
        price_data = defaultdict(list)
        for p in prices_query:
            price_data[p.symbol].append({
                "date": p.date,
                "close": p.close,
            })

        # Calculate returns for each stock
        returns_data = {}
        current_prices = {}
        ma_50 = {}
        ma_200 = {}

        for symbol, prices in price_data.items():
            if len(prices) < 5:
                continue

            df = pd.DataFrame(prices).sort_values("date")
            df["return"] = df["close"].pct_change()

            current_price = df.iloc[-1]["close"]
            current_prices[symbol] = current_price

            # Calculate MAs
            if len(df) >= 50:
                ma_50[symbol] = df["close"].tail(50).mean()
            if len(df) >= 200:
                ma_200[symbol] = df["close"].tail(200).mean()

            # Store returns
            returns_data[symbol] = df.set_index("date")["return"]

        if not returns_data:
            return self._empty_price_metrics()

        # Combine returns into DataFrame
        returns_df = pd.DataFrame(returns_data)

        # Calculate basket returns (equal-weight)
        basket_returns = returns_df.mean(axis=1)

        # Get SPY returns for comparison
        spy_prices = self.db.query(StockPrice).filter(
            StockPrice.symbol == "SPY",
            StockPrice.date >= date_lookback.date(),
            StockPrice.date <= as_of_date.date(),
        ).order_by(StockPrice.date).all()

        spy_df = pd.DataFrame([{"date": p.date, "close": p.close} for p in spy_prices])
        if len(spy_df) > 0:
            spy_df = spy_df.sort_values("date")
            spy_df["return"] = spy_df["close"].pct_change()
            spy_returns = spy_df.set_index("date")["return"]
        else:
            spy_returns = pd.Series()

        # Calculate period returns
        basket_return_1d = basket_returns.iloc[-1] if len(basket_returns) > 0 else 0
        basket_return_1w = basket_returns.tail(5).sum() if len(basket_returns) >= 5 else 0
        basket_return_1m = basket_returns.tail(21).sum() if len(basket_returns) >= 21 else 0

        # Calculate RS vs SPY (1-month cumulative)
        spy_return_1m = spy_returns.tail(21).sum() if len(spy_returns) >= 21 else 0
        relative_return = basket_return_1m - spy_return_1m

        # Convert to RS rating (0-100 scale, 50 = market, 100 = +10% outperformance)
        basket_rs_vs_spy = 50 + (relative_return * 500)  # +1% = 55, +10% = 100
        basket_rs_vs_spy = max(0, min(100, basket_rs_vs_spy))

        # Breadth metrics
        num_above_50ma = sum(1 for s, p in current_prices.items() if s in ma_50 and p > ma_50[s])
        num_above_200ma = sum(1 for s, p in current_prices.items() if s in ma_200 and p > ma_200[s])

        pct_above_50ma = num_above_50ma / len(current_prices) * 100 if current_prices else 0
        pct_above_200ma = num_above_200ma / len(current_prices) * 100 if current_prices else 0

        # % positive on week
        weekly_returns = returns_df.tail(5).sum()
        pct_positive_1w = (weekly_returns > 0).sum() / len(weekly_returns) * 100 if len(weekly_returns) > 0 else 0

        # Internal correlation (average pairwise)
        if len(returns_df.columns) >= 2:
            corr_matrix = returns_df.tail(21).corr()  # 1-month correlation
            # Get upper triangle (excluding diagonal)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            correlations = corr_matrix.where(mask).stack().values
            avg_correlation = np.nanmean(correlations) if len(correlations) > 0 else 0
            correlation_tightness = np.nanstd(correlations) if len(correlations) > 0 else 0
        else:
            avg_correlation = 0
            correlation_tightness = 0

        return {
            "basket_return_1d": round(basket_return_1d * 100, 2),
            "basket_return_1w": round(basket_return_1w * 100, 2),
            "basket_return_1m": round(basket_return_1m * 100, 2),
            "basket_rs_vs_spy": round(basket_rs_vs_spy, 1),
            "pct_above_50ma": round(pct_above_50ma, 1),
            "pct_above_200ma": round(pct_above_200ma, 1),
            "pct_positive_1w": round(pct_positive_1w, 1),
            "avg_internal_correlation": round(avg_correlation, 3),
            "correlation_tightness": round(correlation_tightness, 3),
            "num_constituents": len(symbols),
        }

    def _empty_price_metrics(self) -> dict:
        return {
            "basket_return_1d": 0,
            "basket_return_1w": 0,
            "basket_return_1m": 0,
            "basket_rs_vs_spy": 50,
            "pct_above_50ma": 0,
            "pct_above_200ma": 0,
            "pct_positive_1w": 0,
            "avg_internal_correlation": 0,
            "correlation_tightness": 0,
            "num_constituents": 0,
        }

    def calculate_screener_metrics(self, theme_cluster_id: int) -> dict:
        """
        Calculate metrics from your existing screeners

        Returns count of stocks passing Minervini, stage 2, avg RS
        """
        constituents = self.db.query(ThemeConstituent).filter(
            ThemeConstituent.theme_cluster_id == theme_cluster_id,
            ThemeConstituent.is_active == True,
        ).all()

        if not constituents:
            return {"num_passing_minervini": 0, "num_stage_2": 0, "avg_rs_rating": 0}

        symbols = [c.symbol for c in constituents]

        # Get most recent scan results for these symbols
        # Find latest scan
        from ..models.scan_result import Scan
        latest_scan = self.db.query(Scan).filter(
            Scan.status == "completed"
        ).order_by(Scan.completed_at.desc()).first()

        if not latest_scan:
            return {"num_passing_minervini": 0, "num_stage_2": 0, "avg_rs_rating": 0}

        # Get results for our symbols
        results = self.db.query(ScanResult).filter(
            ScanResult.scan_id == latest_scan.scan_id,
            ScanResult.symbol.in_(symbols),
        ).all()

        if not results:
            return {"num_passing_minervini": 0, "num_stage_2": 0, "avg_rs_rating": 0}

        num_passing_minervini = sum(1 for r in results if r.minervini_score and r.minervini_score >= 70)
        num_stage_2 = sum(1 for r in results if r.stage == 2)
        rs_ratings = [r.rs_rating for r in results if r.rs_rating is not None]
        avg_rs_rating = np.mean(rs_ratings) if rs_ratings else 0

        return {
            "num_passing_minervini": num_passing_minervini,
            "num_stage_2": num_stage_2,
            "avg_rs_rating": round(avg_rs_rating, 1),
        }

    def calculate_composite_score(self, mention_metrics: dict, price_metrics: dict, screener_metrics: dict) -> float:
        """
        Calculate composite theme momentum score (0-100)

        Weighted components (configurable per pipeline):
        - Mention velocity: Social signal strength
        - RS vs SPY: Price momentum
        - Breadth: % above 50MA
        - Internal correlation: Theme cohesiveness
        - Screener quality: % passing Minervini

        Technical pipeline: 30% velocity, 30% RS, 15% breadth, 15% correlation, 10% quality
        Fundamental pipeline: 15% velocity, 20% RS, 25% breadth, 15% correlation, 25% quality
        """
        # Get weights from pipeline config or use defaults
        if self.pipeline_config:
            velocity_weight = self.pipeline_config.velocity_weight
            rs_weight = self.pipeline_config.rs_weight
            breadth_weight = self.pipeline_config.breadth_weight
            correlation_weight = self.pipeline_config.correlation_weight
            quality_weight = self.pipeline_config.quality_weight
        else:
            # Default weights
            velocity_weight = 0.25
            rs_weight = 0.25
            breadth_weight = 0.20
            correlation_weight = 0.15
            quality_weight = 0.15

        # Velocity score (0-100)
        # velocity of 2 = 100, velocity of 1 = 50, velocity of 0.5 = 25
        velocity = mention_metrics.get("mention_velocity", 0)
        velocity_score = min(100, velocity * 50)

        # RS score (already 0-100)
        rs_score = price_metrics.get("basket_rs_vs_spy", 50)

        # Breadth score (already 0-100)
        breadth_score = price_metrics.get("pct_above_50ma", 0)

        # Correlation score (0-100)
        # Correlation of 0.7+ = 100, 0.5 = 70, 0.3 = 40
        correlation = price_metrics.get("avg_internal_correlation", 0)
        correlation_score = min(100, max(0, correlation * 140))

        # Quality score (0-100)
        num_constituents = price_metrics.get("num_constituents", 1)
        num_passing = screener_metrics.get("num_passing_minervini", 0)
        quality_score = (num_passing / num_constituents * 100) if num_constituents > 0 else 0

        # Weighted composite using pipeline-specific weights
        composite = (
            velocity_score * velocity_weight +
            rs_score * rs_weight +
            breadth_score * breadth_weight +
            correlation_score * correlation_weight +
            quality_score * quality_weight
        )

        return round(composite, 1)

    def classify_theme_status(self, composite_score: float, mention_velocity: float, rs_vs_spy: float) -> str:
        """
        Classify theme status based on metrics

        Uses pipeline-specific thresholds for classification.

        Returns: emerging, trending, fading, dormant
        """
        # Get thresholds from pipeline config or use defaults
        if self.pipeline_config:
            trending_min_score = self.pipeline_config.trending_min_score
            trending_min_velocity = self.pipeline_config.trending_min_velocity
            emerging_min_velocity = self.pipeline_config.emerging_min_velocity
            emerging_min_score = self.pipeline_config.emerging_min_score
            fading_max_score = self.pipeline_config.fading_max_score
            fading_max_rs = self.pipeline_config.fading_max_rs
            dormant_max_velocity = self.pipeline_config.dormant_max_velocity
        else:
            # Default thresholds
            trending_min_score = 70.0
            trending_min_velocity = 1.5
            emerging_min_velocity = 2.0
            emerging_min_score = 50.0
            fading_max_score = 40.0
            fading_max_rs = 45.0
            dormant_max_velocity = 0.5

        if composite_score >= trending_min_score and mention_velocity >= trending_min_velocity:
            return "trending"
        elif mention_velocity >= emerging_min_velocity and composite_score >= emerging_min_score:
            return "emerging"
        elif composite_score < fading_max_score and rs_vs_spy < fading_max_rs:
            return "fading"
        elif mention_velocity < dormant_max_velocity:
            return "dormant"
        else:
            return "active"

    def update_theme_metrics(self, theme_cluster_id: int, as_of_date: Optional[datetime] = None) -> ThemeMetrics:
        """
        Calculate and store all metrics for a theme

        Returns the created ThemeMetrics record
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        # Get cluster
        cluster = self.db.query(ThemeCluster).filter(ThemeCluster.id == theme_cluster_id).first()
        if not cluster:
            raise ValueError(f"Theme cluster {theme_cluster_id} not found")

        # Calculate all metrics
        mention_metrics = self.calculate_mention_metrics(theme_cluster_id, as_of_date)
        price_metrics = self.calculate_price_metrics(theme_cluster_id, as_of_date)
        screener_metrics = self.calculate_screener_metrics(theme_cluster_id)

        # Calculate composite
        momentum_score = self.calculate_composite_score(mention_metrics, price_metrics, screener_metrics)

        # Classify status
        status = self.classify_theme_status(
            momentum_score,
            mention_metrics["mention_velocity"],
            price_metrics["basket_rs_vs_spy"]
        )

        # Check for existing metrics for this date
        existing = self.db.query(ThemeMetrics).filter(
            ThemeMetrics.theme_cluster_id == theme_cluster_id,
            ThemeMetrics.date == as_of_date.date(),
        ).first()

        if existing:
            metrics = existing
        else:
            metrics = ThemeMetrics(
                theme_cluster_id=theme_cluster_id,
                date=as_of_date.date(),
                pipeline=self.pipeline,  # Set pipeline from service instance
            )
            self.db.add(metrics)

        # Ensure pipeline is set on existing metrics too
        metrics.pipeline = self.pipeline

        # Update all fields
        metrics.mentions_1d = mention_metrics["mentions_1d"]
        metrics.mentions_7d = mention_metrics["mentions_7d"]
        metrics.mentions_30d = mention_metrics["mentions_30d"]
        metrics.mention_velocity = mention_metrics["mention_velocity"]
        metrics.sentiment_score = mention_metrics["sentiment_score"]

        metrics.basket_return_1d = price_metrics["basket_return_1d"]
        metrics.basket_return_1w = price_metrics["basket_return_1w"]
        metrics.basket_return_1m = price_metrics["basket_return_1m"]
        metrics.basket_rs_vs_spy = price_metrics["basket_rs_vs_spy"]

        metrics.avg_internal_correlation = price_metrics["avg_internal_correlation"]
        metrics.correlation_tightness = price_metrics["correlation_tightness"]

        metrics.num_constituents = price_metrics["num_constituents"]
        metrics.pct_above_50ma = price_metrics["pct_above_50ma"]
        metrics.pct_above_200ma = price_metrics["pct_above_200ma"]
        metrics.pct_positive_1w = price_metrics["pct_positive_1w"]

        metrics.num_passing_minervini = screener_metrics["num_passing_minervini"]
        metrics.num_stage_2 = screener_metrics["num_stage_2"]
        metrics.avg_rs_rating = screener_metrics["avg_rs_rating"]

        metrics.momentum_score = momentum_score
        metrics.status = status

        self.db.commit()

        logger.info(f"Updated metrics for theme '{cluster.name}': score={momentum_score}, status={status}")
        return metrics

    def update_all_theme_metrics(self, as_of_date: Optional[datetime] = None) -> dict:
        """
        Update metrics for all active themes in this pipeline and calculate rankings

        Rankings are calculated separately per pipeline.

        Returns summary of updates
        """
        if as_of_date is None:
            as_of_date = datetime.utcnow()

        # Get all active themes in this pipeline
        clusters = self.db.query(ThemeCluster).filter(
            ThemeCluster.is_active == True,
            ThemeCluster.pipeline == self.pipeline,
        ).all()

        results = {
            "themes_updated": 0,
            "errors": 0,
            "rankings": [],
            "pipeline": self.pipeline,
        }

        metrics_list = []
        for cluster in clusters:
            try:
                metrics = self.update_theme_metrics(cluster.id, as_of_date)
                metrics_list.append((cluster, metrics))
                results["themes_updated"] += 1
            except Exception as e:
                logger.error(f"Error updating metrics for {cluster.name}: {e}")
                results["errors"] += 1

        # Calculate rankings (by momentum score) - separate rankings per pipeline
        metrics_list.sort(key=lambda x: x[1].momentum_score or 0, reverse=True)

        for rank, (cluster, metrics) in enumerate(metrics_list, 1):
            metrics.rank = rank
            results["rankings"].append({
                "rank": rank,
                "theme": cluster.name,
                "score": metrics.momentum_score,
                "status": metrics.status,
            })

        self.db.commit()

        return results

    def get_theme_rankings(
        self,
        limit: int = 20,
        status_filter: Optional[str] = None,
        source_types_filter: Optional[list[str]] = None,
        offset: int = 0
    ) -> tuple[list[dict], int]:
        """
        Get current theme rankings for this pipeline

        Returns tuple of (list of themes with their metrics, total count)

        Args:
            limit: Maximum number of themes to return
            status_filter: Filter by theme status (emerging, trending, fading, dormant)
            source_types_filter: Filter to themes that have mentions from these source types
            offset: Number of themes to skip for pagination
        """
        # Get latest date with metrics for this pipeline
        latest_date = self.db.query(func.max(ThemeMetrics.date)).filter(
            ThemeMetrics.pipeline == self.pipeline
        ).scalar()
        if not latest_date:
            return [], 0

        base_query = self.db.query(ThemeMetrics, ThemeCluster).join(
            ThemeCluster, ThemeMetrics.theme_cluster_id == ThemeCluster.id
        ).filter(
            ThemeMetrics.date == latest_date,
            ThemeCluster.is_active == True,
            ThemeCluster.pipeline == self.pipeline,  # Filter by pipeline
        )

        if status_filter:
            base_query = base_query.filter(ThemeMetrics.status == status_filter)

        # Filter by source types if specified
        if source_types_filter:
            theme_ids_with_sources = self.db.query(ThemeMention.theme_cluster_id).filter(
                ThemeMention.source_type.in_(source_types_filter),
                ThemeMention.pipeline == self.pipeline,  # Filter mentions by pipeline too
            ).distinct().subquery()
            base_query = base_query.filter(ThemeCluster.id.in_(theme_ids_with_sources))

        # Get total count before pagination
        total_count = base_query.count()

        # Apply pagination
        query = base_query.order_by(ThemeMetrics.rank).offset(offset).limit(limit)

        results = []
        for metrics, cluster in query.all():
            # Get top constituents
            top_constituents = self.db.query(ThemeConstituent).filter(
                ThemeConstituent.theme_cluster_id == cluster.id,
                ThemeConstituent.is_active == True,
            ).order_by(ThemeConstituent.mention_count.desc()).limit(15).all()

            results.append({
                "theme_cluster_id": cluster.id,
                "rank": metrics.rank,
                "theme": cluster.name,
                "status": metrics.status,
                "momentum_score": metrics.momentum_score,
                "mention_velocity": metrics.mention_velocity,
                "mentions_7d": metrics.mentions_7d,
                "basket_rs_vs_spy": metrics.basket_rs_vs_spy,
                "basket_return_1w": metrics.basket_return_1w,
                "pct_above_50ma": metrics.pct_above_50ma,
                "avg_correlation": metrics.avg_internal_correlation,
                "num_constituents": metrics.num_constituents,
                "top_tickers": [c.symbol for c in top_constituents],
                "first_seen": cluster.first_seen_at.isoformat() if cluster.first_seen_at else None,
            })

        return results, total_count

    def discover_emerging_themes(self, min_velocity: float = 1.5, min_mentions: int = 3) -> list[dict]:
        """
        Find newly emerging themes for this pipeline

        Criteria:
        - First seen in last 7 days
        - Mention velocity > min_velocity
        - At least min_mentions mentions
        """
        week_ago = datetime.utcnow() - timedelta(days=7)

        emerging = self.db.query(ThemeCluster).filter(
            ThemeCluster.is_active == True,
            ThemeCluster.first_seen_at >= week_ago,
            ThemeCluster.pipeline == self.pipeline,  # Filter by pipeline
        ).all()

        results = []
        for cluster in emerging:
            mention_metrics = self.calculate_mention_metrics(cluster.id)

            if mention_metrics["mentions_7d"] >= min_mentions and mention_metrics["mention_velocity"] >= min_velocity:
                # Get constituents
                constituents = self.db.query(ThemeConstituent).filter(
                    ThemeConstituent.theme_cluster_id == cluster.id,
                ).order_by(ThemeConstituent.mention_count.desc()).limit(10).all()

                results.append({
                    "theme": cluster.name,
                    "first_seen": cluster.first_seen_at.isoformat(),
                    "mentions_7d": mention_metrics["mentions_7d"],
                    "velocity": mention_metrics["mention_velocity"],
                    "sentiment": mention_metrics["sentiment_score"],
                    "tickers": [c.symbol for c in constituents],
                })

        # Sort by velocity
        results.sort(key=lambda x: x["velocity"], reverse=True)
        return results

    def create_alert(
        self,
        alert_type: str,
        title: str,
        description: str,
        theme_cluster_id: Optional[int] = None,
        tickers: Optional[list] = None,
        metrics: Optional[dict] = None,
        severity: str = "info",
    ) -> ThemeAlert:
        """Create a theme alert"""
        alert = ThemeAlert(
            theme_cluster_id=theme_cluster_id,
            alert_type=alert_type,
            title=title,
            description=description,
            severity=severity,
            related_tickers=tickers or [],
            metrics=metrics or {},
        )
        self.db.add(alert)
        self.db.commit()
        return alert

    def check_for_alerts(self) -> list[ThemeAlert]:
        """
        Check for alert conditions and create alerts

        Alert types:
        - new_theme: Theme discovered in last 24h
        - velocity_spike: Velocity > 3x normal
        - breakout: RS breakout above 70
        - theme_confirmed: New theme validated by correlation
        """
        alerts = []
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)

        # New themes in last 24h
        new_themes = self.db.query(ThemeCluster).filter(
            ThemeCluster.first_seen_at >= day_ago,
        ).all()

        for theme in new_themes:
            # Check if alert already exists
            existing = self.db.query(ThemeAlert).filter(
                ThemeAlert.theme_cluster_id == theme.id,
                ThemeAlert.alert_type == "new_theme",
            ).first()

            if not existing:
                constituents = self.db.query(ThemeConstituent).filter(
                    ThemeConstituent.theme_cluster_id == theme.id
                ).all()

                alert = self.create_alert(
                    alert_type="new_theme",
                    title=f"New Theme Discovered: {theme.name}",
                    description=f"New market theme '{theme.name}' detected from social/news sources.",
                    theme_cluster_id=theme.id,
                    tickers=[c.symbol for c in constituents[:5]],
                    severity="info",
                )
                alerts.append(alert)

        # Velocity spikes
        latest_date = self.db.query(func.max(ThemeMetrics.date)).scalar()
        if latest_date:
            velocity_spikes = self.db.query(ThemeMetrics, ThemeCluster).join(
                ThemeCluster, ThemeMetrics.theme_cluster_id == ThemeCluster.id
            ).filter(
                ThemeMetrics.date == latest_date,
                ThemeMetrics.mention_velocity >= 3.0,
            ).all()

            for metrics, theme in velocity_spikes:
                existing = self.db.query(ThemeAlert).filter(
                    ThemeAlert.theme_cluster_id == theme.id,
                    ThemeAlert.alert_type == "velocity_spike",
                    ThemeAlert.triggered_at >= day_ago,
                ).first()

                if not existing:
                    alert = self.create_alert(
                        alert_type="velocity_spike",
                        title=f"Velocity Spike: {theme.name}",
                        description=f"Theme '{theme.name}' is seeing {metrics.mention_velocity:.1f}x normal mention rate.",
                        theme_cluster_id=theme.id,
                        metrics={"velocity": metrics.mention_velocity, "mentions_7d": metrics.mentions_7d},
                        severity="warning",
                    )
                    alerts.append(alert)

        return alerts
