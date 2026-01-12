"""
Pipeline Configuration for Theme Discovery

Defines separate configurations for Technical and Fundamental pipelines:
- Technical: Price action, momentum, RS, chart patterns, breakouts
- Fundamental: Earnings, valuation, macro themes, analyst coverage
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineConfig:
    """Configuration for a theme analysis pipeline"""

    # Identity
    name: str
    display_name: str
    description: str

    # LLM extraction customization
    extraction_prompt_additions: str = ""
    theme_examples: list[str] = field(default_factory=list)

    # Scoring weights (must sum to 1.0)
    velocity_weight: float = 0.25
    rs_weight: float = 0.25
    breadth_weight: float = 0.20
    correlation_weight: float = 0.15
    quality_weight: float = 0.15

    # Status classification thresholds
    trending_min_score: float = 70.0
    trending_min_velocity: float = 1.5
    emerging_min_velocity: float = 2.0
    emerging_min_score: float = 50.0
    fading_max_score: float = 40.0
    fading_max_rs: float = 45.0
    dormant_max_velocity: float = 0.5


# Technical Pipeline Configuration
TECHNICAL_PIPELINE = PipelineConfig(
    name="technical",
    display_name="Technical",
    description="Price action, momentum, RS, chart patterns, breakouts",

    extraction_prompt_additions="""
FOCUS ON TECHNICAL/PRICE-ACTION THEMES:
- Stage 2 breakouts and momentum plays
- Relative strength leaders
- Chart pattern setups (cup & handle, VCP, etc.)
- Price/volume breakouts
- Sector rotation plays
- Moving average trends

AVOID extracting fundamental-only themes like:
- Earnings surprises (unless causing technical breakout)
- Valuation-based plays
- Pure macro economic themes
""",

    theme_examples=[
        "AI Infrastructure Breakouts",
        "Semiconductor RS Leaders",
        "Defense Sector Stage 2",
        "Nuclear Energy Momentum",
        "Bitcoin Miners Breakout",
        "China Tech Recovery",
        "Small Cap Momentum",
        "High RS Growth Stocks",
    ],

    # Technical pipeline weights - emphasize velocity and RS
    velocity_weight=0.30,
    rs_weight=0.30,
    breadth_weight=0.15,
    correlation_weight=0.15,
    quality_weight=0.10,

    # Technical thresholds - higher bar for trending
    trending_min_score=70.0,
    trending_min_velocity=1.5,
    emerging_min_velocity=2.0,
    emerging_min_score=50.0,
    fading_max_score=40.0,
    fading_max_rs=45.0,
    dormant_max_velocity=0.5,
)


# Fundamental Pipeline Configuration
FUNDAMENTAL_PIPELINE = PipelineConfig(
    name="fundamental",
    display_name="Fundamental",
    description="Earnings, valuation, macro themes, analyst coverage",

    extraction_prompt_additions="""
FOCUS ON FUNDAMENTAL/MACRO THEMES:
- Earnings growth stories (EPS acceleration, revenue beats)
- Valuation plays (value rotations, multiple expansion)
- Macro economic themes (inflation, rates, GDP)
- Analyst upgrades and estimate revisions
- Industry tailwinds (regulatory, competitive)
- M&A and corporate events
- Dividend growth themes
- FDA approvals and drug pipelines

AVOID extracting pure technical themes like:
- Chart patterns
- Moving average signals
- Volume breakouts (unless tied to fundamental catalyst)
""",

    theme_examples=[
        "AI Capex Beneficiaries",
        "GLP-1 Drug Pipeline",
        "EPS Revision Leaders",
        "Dividend Aristocrats",
        "FDA Approval Candidates",
        "Nearshoring Beneficiaries",
        "Rate Cut Winners",
        "Inflation Hedge Plays",
    ],

    # Fundamental pipeline weights - emphasize breadth and quality
    velocity_weight=0.15,
    rs_weight=0.20,
    breadth_weight=0.25,
    correlation_weight=0.15,
    quality_weight=0.25,

    # Fundamental thresholds - lower velocity requirements
    trending_min_score=65.0,
    trending_min_velocity=1.2,
    emerging_min_velocity=1.5,
    emerging_min_score=45.0,
    fading_max_score=35.0,
    fading_max_rs=42.0,
    dormant_max_velocity=0.4,
)


# Pipeline registry
PIPELINE_CONFIGS: dict[str, PipelineConfig] = {
    "technical": TECHNICAL_PIPELINE,
    "fundamental": FUNDAMENTAL_PIPELINE,
}


def get_pipeline_config(pipeline_name: str) -> PipelineConfig:
    """Get pipeline configuration by name"""
    if pipeline_name not in PIPELINE_CONFIGS:
        raise ValueError(f"Unknown pipeline: {pipeline_name}. Valid options: {list(PIPELINE_CONFIGS.keys())}")
    return PIPELINE_CONFIGS[pipeline_name]


def get_all_pipelines() -> list[dict]:
    """Get list of all available pipelines for API response"""
    return [
        {
            "name": config.name,
            "display_name": config.display_name,
            "description": config.description,
        }
        for config in PIPELINE_CONFIGS.values()
    ]
