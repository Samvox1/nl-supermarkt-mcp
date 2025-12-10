# NL Supermarkt MCP Server

Een Model Context Protocol (MCP) server voor Nederlandse supermarkt data. Vergelijk prijzen, bekijk aanbiedingen, en plan je boodschappen met recepten.

## Features

- **Prijsvergelijking**: Vergelijk prijzen van 100.000+ producten bij 12+ supermarkten
- **Folder aanbiedingen**: Actuele aanbiedingen van Albert Heijn, Jumbo, Lidl, Vomar, etc.
- **Recepten database**: 75+ recepten met ingrediënten en bereiding
- **Boodschappenplanner**: Weekmenu met recepten op basis van aanbiedingen

## Quick Start met Docker

### 1. Clone de repository

```bash
git clone https://github.com/yourusername/nl-supermarkt-mcp.git
cd nl-supermarkt-mcp
```

### 2. Start de services

```bash
docker compose up -d
```

Dit start:
- PostgreSQL database
- MCP server op poort 8000
- Data sync (haalt prijzen, aanbiedingen en recepten op)

### 3. Wacht op data sync (eerste keer ~5 minuten)

```bash
# Volg de sync progress
docker compose logs -f data-sync

# Check of alles draait
docker compose ps
```

### 4. Configureer Claude Desktop

Voeg toe aan `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nl-supermarkt": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/sse", "--allow-http"]
    }
  }
}
```

### 5. Herstart Claude Desktop

De server is nu beschikbaar!

## Beschikbare Tools

| Tool | Beschrijving |
|------|-------------|
| `zoek_producten` | Zoek producten op naam |
| `vergelijk_prijzen` | Vergelijk prijzen bij supermarkten |
| `bekijk_aanbiedingen` | Bekijk folder aanbiedingen |
| `zoek_recepten` | Zoek recepten |
| `plan_boodschappen` | Plan weekmenu met boodschappenlijst |
| `optimaliseer_boodschappenlijst` | Optimaliseer een boodschappenlijst |
| `lijst_supermarkten` | Toon beschikbare supermarkten |

## Voorbeeld Queries

```
# Zoek producten
"Zoek melk bij Albert Heijn"

# Vergelijk prijzen
"Vergelijk de prijs van pindakaas"

# Bekijk aanbiedingen
"Wat zijn de aanbiedingen bij Jumbo voor pasta?"

# Plan boodschappen
"Plan boodschappen voor 4 dagen, 2 personen, bij AH en Jumbo, voorkeur voor pasta"
```

## Data Updates

Data wordt automatisch bijgewerkt:
- Prijzen: dagelijks
- Aanbiedingen: 2x per dag
- Recepten: wekelijks

Handmatig updaten:

```bash
docker compose run --rm data-sync
```

## Environment Variables

| Variable | Default | Beschrijving |
|----------|---------|--------------|
| `DB_HOST` | db | Database host |
| `DB_PORT` | 5432 | Database poort |
| `DB_NAME` | supermarkt_db | Database naam |
| `DB_USER` | postgres | Database gebruiker |
| `DB_PASSWORD` | supermarkt123 | Database wachtwoord |
| `PORT` | 8000 | MCP server poort |

## Development

### Lokaal draaien (zonder Docker)

```bash
# Maak venv
python -m venv venv
source venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt

# Start PostgreSQL (bijvoorbeeld via brew)
brew services start postgresql

# Maak database
createdb supermarkt_db
psql supermarkt_db < docker/init.sql

# Sync data
python sync_prices.py
python sync_folderz.py
python sync_recepten.py

# Start server
python src/server_sse.py
```

### Project structuur

```
nl-supermarkt-mcp/
├── docker-compose.yml      # Docker compose config
├── Dockerfile              # MCP server image
├── Dockerfile.sync         # Data sync image
├── docker/
│   ├── init.sql           # Database schema
│   └── sync_all.py        # Master sync script
├── src/
│   ├── server.py          # MCP server logic
│   └── server_sse.py      # SSE transport wrapper
├── sync_prices.py         # Prijzen sync (Checkjebon.nl)
├── sync_folderz.py        # Aanbiedingen sync (Folderz.nl)
└── sync_recepten.py       # Recepten sync (TheMealDB + eigen)
```

## Data Bronnen

- **Prijzen**: [Checkjebon.nl](https://checkjebon.nl) - 100.000+ producten
- **Aanbiedingen**: [Folderz.nl](https://folderz.nl) - Folder aanbiedingen
- **Recepten**: [TheMealDB](https://themealdb.com) + eigen Nederlandse recepten

## Licentie

MIT

## Credits

- MCP protocol by Anthropic
- Data van Checkjebon.nl en Folderz.nl
- Recepten van TheMealDB
