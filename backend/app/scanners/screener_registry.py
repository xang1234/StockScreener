"""
Screener registry for managing available screening strategies.

Provides a central registry where screeners can register themselves
and be retrieved by name. This enables dynamic screener selection
based on user requests.
"""
from typing import Dict, List, Optional, Type
from .base_screener import BaseStockScreener


class ScreenerRegistry:
    """
    Central registry for all available screeners.

    Screeners register themselves with the registry, and can be
    retrieved by name. This enables the orchestrator to dynamically
    select and instantiate screeners based on user requests.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._screeners: Dict[str, Type[BaseStockScreener]] = {}

    def register(self, screener_class: Type[BaseStockScreener]) -> None:
        """
        Register a screener class.

        Args:
            screener_class: Screener class (not instance) to register

        Raises:
            ValueError: If screener with same name already registered
        """
        # Instantiate temporarily to get the name
        temp_instance = screener_class()
        name = temp_instance.screener_name

        if name in self._screeners:
            existing = self._screeners[name]
            if existing != screener_class:
                raise ValueError(
                    f"Screener '{name}' already registered with class {existing.__name__}. "
                    f"Cannot register {screener_class.__name__}"
                )
            # Same class re-registered, ignore
            return

        self._screeners[name] = screener_class
        print(f"Registered screener: {name} ({screener_class.__name__})")

    def get(self, name: str) -> Optional[BaseStockScreener]:
        """
        Get a screener instance by name.

        Args:
            name: Screener name (e.g., "minervini", "canslim")

        Returns:
            New instance of the screener, or None if not found
        """
        screener_class = self._screeners.get(name)
        if screener_class is None:
            return None
        return screener_class()

    def get_multiple(self, names: List[str]) -> Dict[str, BaseStockScreener]:
        """
        Get multiple screener instances by name.

        Args:
            names: List of screener names

        Returns:
            Dict mapping name to screener instance

        Raises:
            ValueError: If any screener name is not found
        """
        screeners = {}
        missing = []

        for name in names:
            screener = self.get(name)
            if screener is None:
                missing.append(name)
            else:
                screeners[name] = screener

        if missing:
            available = list(self._screeners.keys())
            raise ValueError(
                f"Unknown screeners: {missing}. Available screeners: {available}"
            )

        return screeners

    def is_registered(self, name: str) -> bool:
        """
        Check if a screener is registered.

        Args:
            name: Screener name

        Returns:
            True if registered
        """
        return name in self._screeners

    def list_screeners(self) -> List[str]:
        """
        List all registered screener names.

        Returns:
            List of screener names
        """
        return sorted(self._screeners.keys())

    def clear(self) -> None:
        """Clear all registered screeners (mainly for testing)."""
        self._screeners.clear()

    def __len__(self) -> int:
        """Number of registered screeners."""
        return len(self._screeners)

    def __contains__(self, name: str) -> bool:
        """Check if screener is registered using 'in' operator."""
        return name in self._screeners

    def __str__(self) -> str:
        """String representation."""
        screeners = ", ".join(self.list_screeners())
        return f"ScreenerRegistry({len(self)} screeners: {screeners})"


# Global singleton registry instance
screener_registry = ScreenerRegistry()


# Decorator for easy registration
def register_screener(screener_class: Type[BaseStockScreener]) -> Type[BaseStockScreener]:
    """
    Decorator to automatically register a screener.

    Usage:
        @register_screener
        class MyScanner(BaseStockScreener):
            ...

    Args:
        screener_class: Screener class to register

    Returns:
        The same class (for chaining)
    """
    screener_registry.register(screener_class)
    return screener_class
