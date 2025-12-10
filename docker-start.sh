#!/bin/bash
# NL Supermarkt MCP - Docker Quick Start
# Usage: ./docker-start.sh

set -e

echo "🛒 NL Supermarkt MCP Server - Docker Setup"
echo "==========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is niet geïnstalleerd!"
    echo "   Installeer Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✅ Docker gevonden"

# Build the image
echo ""
echo "📦 Docker image bouwen..."
docker build -t nl-supermarkt-mcp .

echo ""
echo "✅ Image gebouwd!"
echo ""
echo "==========================================="
echo "🚀 Klaar! Gebruik een van deze commando's:"
echo ""
echo "   # Start server (interactive):"
echo "   docker run -it --rm nl-supermarkt-mcp"
echo ""
echo "   # Start server (background):"
echo "   docker run -d --name supermarkt-mcp nl-supermarkt-mcp"
echo ""
echo "   # Met docker-compose:"
echo "   docker-compose up -d"
echo ""
echo "   # Stop:"
echo "   docker-compose down"
echo "==========================================="
