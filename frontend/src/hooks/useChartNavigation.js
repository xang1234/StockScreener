import { useState, useEffect } from 'react';

/**
 * Custom hook for keyboard-based chart navigation
 *
 * @param {Array<string>} symbols - Complete list of symbols to navigate through
 * @param {string} initialSymbol - Symbol to start with
 * @param {boolean} isOpen - Whether the modal is currently open
 * @returns {Object} Navigation state and functions
 */
export const useChartNavigation = (symbols, initialSymbol, isOpen) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentSymbol, setCurrentSymbol] = useState(initialSymbol);

  // Immediately set currentSymbol when modal opens with initialSymbol
  // This ensures the chart can render before the symbols list loads
  useEffect(() => {
    if (isOpen && initialSymbol) {
      setCurrentSymbol(initialSymbol);
    }
  }, [isOpen, initialSymbol]);

  // Find and set the correct index once symbols list loads
  useEffect(() => {
    if (isOpen && symbols && symbols.length > 0 && initialSymbol) {
      const index = symbols.indexOf(initialSymbol);
      if (index >= 0) {
        setCurrentIndex(index);
      }
    }
  }, [symbols, initialSymbol, isOpen]);

  // Update currentSymbol whenever index changes (for navigation)
  useEffect(() => {
    if (symbols && symbols.length > 0 && symbols[currentIndex]) {
      setCurrentSymbol(symbols[currentIndex]);
    }
  }, [currentIndex, symbols]);

  // Reset when modal closes
  useEffect(() => {
    if (!isOpen) {
      setCurrentIndex(0);
      setCurrentSymbol(null);
    }
  }, [isOpen]);

  const goNext = () => {
    if (!symbols || symbols.length === 0) return;
    setCurrentIndex((prev) => (prev < symbols.length - 1 ? prev + 1 : 0));
  };

  const goPrevious = () => {
    if (!symbols || symbols.length === 0) return;
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : symbols.length - 1));
  };

  const goToIndex = (index) => {
    if (!symbols || symbols.length === 0) return;
    if (index >= 0 && index < symbols.length) {
      setCurrentIndex(index);
    }
  };

  return {
    currentIndex,
    currentSymbol,
    totalCount: symbols ? symbols.length : 0,
    goNext,
    goPrevious,
    goToIndex,
  };
};
