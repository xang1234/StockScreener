"""
Tool definitions for Groq's native tool calling API.
All tools are defined in OpenAI-compatible format.
"""
from typing import List, Dict, Any, Optional

# YFinance Tools
YFINANCE_QUOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "yfinance_quote",
        "description": "Get current stock price, market cap, P/E ratio, sector, and industry from Yahoo Finance. Use this for any question about a stock's current price or basic info.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., NVDA, AAPL, MSFT, TSLA)"
                }
            },
            "required": ["symbol"]
        }
    }
}

YFINANCE_FUNDAMENTALS_TOOL = {
    "type": "function",
    "function": {
        "name": "yfinance_fundamentals",
        "description": "Get detailed fundamental metrics including P/E, PEG, profit margins, ROE, ROA, revenue growth, debt ratios, and institutional ownership. Use for fundamental analysis or valuation questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                }
            },
            "required": ["symbol"]
        }
    }
}

YFINANCE_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "yfinance_history",
        "description": "Get historical price data with 52-week high/low, moving averages (MA50, MA200), and returns over 1 month, 3 months, 6 months, and YTD. Use for price performance or technical analysis questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "period": {
                    "type": "string",
                    "description": "Time period for history: 1mo, 3mo, 6mo, 1y, 2y. Default is 3mo.",
                    "enum": ["1mo", "3mo", "6mo", "1y", "2y"]
                }
            },
            "required": ["symbol"]
        }
    }
}

YFINANCE_EARNINGS_TOOL = {
    "type": "function",
    "function": {
        "name": "yfinance_earnings",
        "description": "Get recent earnings history (last 4 quarters) and upcoming earnings dates. Use for earnings-related questions or to find when a company reports.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                }
            },
            "required": ["symbol"]
        }
    }
}

COMPARE_STOCKS_TOOL = {
    "type": "function",
    "function": {
        "name": "compare_stocks",
        "description": "Compare multiple stocks side by side on key metrics including price, market cap, P/E, PEG, revenue growth, profit margin, and returns. Use when user wants to compare 2-5 stocks.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock ticker symbols to compare (max 5)",
                    "maxItems": 5
                }
            },
            "required": ["symbols"]
        }
    }
}

# Database Tools (internal stock scanner data)
GET_SCAN_RESULTS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_scan_results",
        "description": "Get internal stock scanner results including composite score, RS rating, stage classification, and technical ratings. May return empty if scanner hasn't run recently.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                }
            },
            "required": ["symbol"]
        }
    }
}

SEARCH_STOCKS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_stocks",
        "description": "Search stocks by criteria such as minimum score, RS rating, stage, sector, or industry. Returns filtered list of stocks from the scanner database.",
        "parameters": {
            "type": "object",
            "properties": {
                "min_score": {
                    "type": "number",
                    "description": "Minimum composite score (0-100)"
                },
                "min_rs_rating": {
                    "type": "number",
                    "description": "Minimum relative strength rating (0-99)"
                },
                "stage": {
                    "type": "string",
                    "description": "Stock stage (e.g., Stage 2 Uptrend, Stage 3 Top, Stage 4 Decline)"
                },
                "sector": {
                    "type": "string",
                    "description": "GICS sector name"
                },
                "industry_group": {
                    "type": "string",
                    "description": "Industry group name"
                },
                "rating": {
                    "type": "string",
                    "description": "Rating filter (Strong Buy, Buy, Hold, Sell)",
                    "enum": ["Strong Buy", "Buy", "Hold", "Sell"]
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20
                }
            },
            "required": []
        }
    }
}

GET_THEME_DATA_TOOL = {
    "type": "function",
    "function": {
        "name": "get_theme_data",
        "description": "Get market theme information including constituent stocks and theme metrics. Use for questions about investment themes like AI, semiconductors, EVs, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "theme_name": {
                    "type": "string",
                    "description": "Theme name to search for (e.g., AI, semiconductors, cloud, EVs)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of themes to return (default 10)",
                    "default": 10
                }
            },
            "required": []
        }
    }
}

GET_TRENDING_THEMES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_trending_themes",
        "description": "Get currently trending investment themes based on velocity and momentum. Use when user asks about hot themes or what's trending in the market.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of themes to return (default 10)",
                    "default": 10
                }
            },
            "required": []
        }
    }
}

GET_BREADTH_DATA_TOOL = {
    "type": "function",
    "function": {
        "name": "get_breadth_data",
        "description": "Get market breadth indicators including advance/decline ratio, new highs/lows, and McClellan oscillator. Use for questions about overall market health.",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Time period: 1d, 1w, 1m (default 1m)",
                    "enum": ["1d", "1w", "1m"]
                },
                "market": {
                    "type": "string",
                    "description": "Market to check: NYSE, NASDAQ, or ALL (default NYSE)",
                    "enum": ["NYSE", "NASDAQ", "ALL"]
                }
            },
            "required": []
        }
    }
}

GET_TOP_RATED_STOCKS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_top_rated_stocks",
        "description": "Get top-rated stocks from the latest scanner run. Use when user asks for best stocks or top picks.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of stocks to return (default 10)",
                    "default": 10
                },
                "rating": {
                    "type": "string",
                    "description": "Rating filter (default Strong Buy)",
                    "enum": ["Strong Buy", "Buy", "Hold"],
                    "default": "Strong Buy"
                }
            },
            "required": []
        }
    }
}

# Database Fundamentals Tool
GET_DB_FUNDAMENTALS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_db_fundamentals",
        "description": "Get comprehensive cached fundamentals data including EPS rating, insider ownership, short interest, company descriptions, performance metrics, and analyst recommendations. Use this for detailed fundamental analysis without external API calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., NVDA, AAPL, MSFT)"
                }
            },
            "required": ["symbol"]
        }
    }
}

# Database Price History Tool
GET_DB_PRICE_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_db_price_history",
        "description": "Get cached historical OHLCV price data from the internal database. Use for price history queries without external API calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default 30, max 365)",
                    "default": 30
                }
            },
            "required": ["symbol"]
        }
    }
}

# Advanced Stock Search Tool
ADVANCED_STOCK_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "advanced_stock_search",
        "description": "Search stocks with advanced fundamental criteria including EPS rating, PE ratio, profit margin, revenue growth, ROE, and sector. Use for finding stocks matching specific fundamental criteria.",
        "parameters": {
            "type": "object",
            "properties": {
                "min_eps_rating": {
                    "type": "integer",
                    "description": "Minimum EPS rating (0-99, IBD-style percentile)"
                },
                "max_pe": {
                    "type": "number",
                    "description": "Maximum P/E ratio"
                },
                "min_profit_margin": {
                    "type": "number",
                    "description": "Minimum profit margin (as decimal, e.g., 0.15 for 15%)"
                },
                "min_revenue_growth": {
                    "type": "number",
                    "description": "Minimum revenue growth rate (as decimal, e.g., 0.20 for 20%)"
                },
                "min_roe": {
                    "type": "number",
                    "description": "Minimum return on equity (as decimal)"
                },
                "sector": {
                    "type": "string",
                    "description": "GICS sector to filter by (e.g., Technology, Healthcare, Consumer Cyclical)"
                },
                "has_description": {
                    "type": "boolean",
                    "description": "Only include stocks with company descriptions available"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default 20)",
                    "default": 20
                }
            },
            "required": []
        }
    }
}

# Web Search Tools
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for general information. Use for recent news, events, analyst opinions, or any information not available in the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
}

SEARCH_NEWS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_news",
        "description": "Search for recent news articles. Use when user specifically asks about news or recent developments for a stock or topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "News search query (e.g., 'NVDA earnings news', 'Tesla recall')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
}

SEARCH_FINANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_finance",
        "description": "Search with finance/investing context. Use for analyst ratings, price targets, market analysis, or financial commentary.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Finance-focused search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
}

# Document Tools (SEC Filings and IR PDFs)
GET_SEC_10K_TOOL = {
    "type": "function",
    "function": {
        "name": "get_sec_10k",
        "description": "Fetch SEC 10-K annual filing for a company. Use for business description, risk factors, financials, MD&A, and detailed company information. For large documents, provide a query to search specific sections.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., NVDA, AAPL, MSFT)"
                },
                "year": {
                    "type": "integer",
                    "description": "Fiscal year (defaults to most recent if not specified)"
                },
                "query": {
                    "type": "string",
                    "description": "Search query for large documents (e.g., 'risk factors', 'revenue growth', 'competition')"
                }
            },
            "required": ["symbol"]
        }
    }
}

READ_IR_PDF_TOOL = {
    "type": "function",
    "function": {
        "name": "read_ir_pdf",
        "description": "Read and analyze a PDF from an investor relations URL. Use for earnings presentations, investor decks, annual reports, and other IR documents. Provide a query for targeted search in large documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Direct URL to the PDF document"
                },
                "query": {
                    "type": "string",
                    "description": "Search query for large documents (e.g., 'revenue guidance', 'market share', 'key metrics')"
                }
            },
            "required": ["url"]
        }
    }
}

# Theme Research Tools
RESEARCH_THEME_TOOL = {
    "type": "function",
    "function": {
        "name": "research_theme",
        "description": "Deep research on a specific investment theme. Returns comprehensive data including theme metrics, constituent stocks, source articles that identified the theme, and optional historical data. Use for questions like 'Tell me about the AI theme' or 'Research the nuclear energy investment theme'.",
        "parameters": {
            "type": "object",
            "properties": {
                "theme_name": {
                    "type": "string",
                    "description": "Theme name to research (e.g., 'AI', 'Nuclear', 'GLP-1', 'Semiconductors')"
                },
                "include_sources": {
                    "type": "boolean",
                    "description": "Include source articles/posts that led to theme discovery (default true)",
                    "default": True
                },
                "include_history": {
                    "type": "boolean",
                    "description": "Include 30-day historical metrics (default false)",
                    "default": False
                },
                "max_sources": {
                    "type": "integer",
                    "description": "Maximum source articles to return (default 10)",
                    "default": 10
                },
                "max_constituents": {
                    "type": "integer",
                    "description": "Maximum constituent tickers to return (default 20)",
                    "default": 20
                }
            },
            "required": ["theme_name"]
        }
    }
}

DISCOVER_THEMES_TOOL = {
    "type": "function",
    "function": {
        "name": "discover_themes",
        "description": "Find and compare investment themes. Use for discovering emerging themes, finding trending themes, or comparing multiple themes side by side. Use for questions like 'What themes are emerging?' or 'Compare AI vs Nuclear themes'.",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["emerging", "trending", "compare"],
                    "description": "Discovery mode: 'emerging' for newly discovered high-velocity themes, 'trending' for current high-momentum themes, 'compare' for side-by-side comparison of specific themes"
                },
                "theme_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Theme names to compare (required for 'compare' mode, e.g., ['AI', 'Nuclear', 'GLP-1'])"
                },
                "min_velocity": {
                    "type": "number",
                    "description": "For emerging mode - minimum 7d/30d mention velocity ratio (default 1.0)",
                    "default": 1.0
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (technology, healthcare, macro, sector, commodity)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum themes to return (default 10)",
                    "default": 10
                }
            },
            "required": ["mode"]
        }
    }
}


# All tools combined for the agent
CHATBOT_TOOLS: List[Dict[str, Any]] = [
    # YFinance tools (always work - external data)
    YFINANCE_QUOTE_TOOL,
    YFINANCE_FUNDAMENTALS_TOOL,
    YFINANCE_HISTORY_TOOL,
    YFINANCE_EARNINGS_TOOL,
    COMPARE_STOCKS_TOOL,
    # Database tools (internal scanner data)
    GET_SCAN_RESULTS_TOOL,
    SEARCH_STOCKS_TOOL,
    GET_THEME_DATA_TOOL,
    GET_TRENDING_THEMES_TOOL,
    GET_BREADTH_DATA_TOOL,
    GET_TOP_RATED_STOCKS_TOOL,
    # New database tools (internal data)
    GET_DB_FUNDAMENTALS_TOOL,
    GET_DB_PRICE_HISTORY_TOOL,
    ADVANCED_STOCK_SEARCH_TOOL,
    # Theme research tools (deep research)
    RESEARCH_THEME_TOOL,
    DISCOVER_THEMES_TOOL,
    # Web search tools
    WEB_SEARCH_TOOL,
    SEARCH_NEWS_TOOL,
    SEARCH_FINANCE_TOOL,
    # Document tools (SEC filings and IR PDFs)
    GET_SEC_10K_TOOL,
    READ_IR_PDF_TOOL,
]


def get_tool_names() -> List[str]:
    """Get list of all tool names."""
    return [tool["function"]["name"] for tool in CHATBOT_TOOLS]


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Get a tool definition by name."""
    for tool in CHATBOT_TOOLS:
        if tool["function"]["name"] == name:
            return tool
    return None
