#!/usr/bin/env bash
set -euo pipefail

echo "Docker disk usage (before):"
docker system df

echo ""
echo "Pruning unused Docker images/containers/networks/build cache..."
docker system prune -af

echo ""
echo "Pruning Docker build cache..."
docker builder prune -af

echo ""
echo "Docker disk usage (after):"
docker system df
