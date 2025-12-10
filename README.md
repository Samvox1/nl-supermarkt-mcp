# NL Supermarkt MCP Server

MCP (Model Context Protocol) server voor Nederlandse supermarkt prijsvergelijking, boodschappenplanning en budget tracking.

## Features

### Basis Functionaliteiten
- **Producten zoeken** - Zoek producten bij 12+ Nederlandse supermarkten
- **Prijsvergelijking** - Vergelijk prijzen tussen supermarkten
- **Boodschappenlijst optimalisatie** - Vind goedkoopste combinatie
- **Folder aanbiedingen** - Bekijk actuele aanbiedingen met promo types (1+1, 2e halve prijs, etc.)
- **Recepten zoeken** - Zoek recepten met dieetfilters (vegetarisch, vegan, glutenvrij)
- **Weekmenu planning** - Plan maaltijden met automatische boodschappenlijst

### Nieuwe Features (v2.0)

#### 1. Prijshistorie & Alerts
- `prijshistorie` - Bekijk prijsverloop, laagste prijs ooit, trends
- `prijs_alert` - Stel alerts in voor producten onder bepaalde prijs
- `check_alerts` - Check welke alerts nu een goede deal zijn

#### 2. Slimme Boodschappenlijst
- `bewaar_boodschappenlijst` - Sla lijsten op voor hergebruik
- `laad_boodschappenlijst` - Laad lijst met actuele prijzen & aanbiedingen
- `lijst_boodschappenlijsten` - Overzicht opgeslagen lijsten
- `wacht_met_kopen` - Advies: nu kopen of wachten op aanbieding?

#### 3. Winkel Routeplanner
- `vind_winkels` - Vind dichtstbijzijnde supermarkten
- `plan_winkelroute` - Optimale route langs meerdere winkels

#### 4. Budget Tracking
- `set_budget` - Stel weekbudget in
- `budget_check` - Check of boodschappen binnen budget passen
- `bespaar_tips` - Persoonlijke bespaartips

## Quick Start

```bash
# Clone repository
git clone https://github.com/Samvox1/nl-supermarkt-mcp.git
cd nl-supermarkt-mcp

# Start met Docker Compose
docker compose up -d

# Eerste data sync (duurt ~2 minuten)
docker compose run --rm data-sync
```

## Claude Desktop Configuratie

Voeg toe aan `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nl-supermarkt": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8000/sse", "--allow-http"]
    }
  }
}
```

## Beschikbare Supermarkten

| Code | Naam | Producten |
|------|------|-----------|
| ah | Albert Heijn | ~15.000 |
| jumbo | Jumbo | ~17.000 |
| lidl | Lidl | ~16.000 |
| aldi | Aldi | ~1.600 |
| plus | Plus | ~14.000 |
| dekamarkt | DekaMarkt | ~10.000 |
| dirk | Dirk | ~7.000 |
| vomar | Vomar | ~900 |
| hoogvliet | Hoogvliet | ~7.000 |
| spar | Spar | ~7.700 |
| picnic | Picnic | - |
| poiesz | Poiesz | ~1.800 |

## Voorbeeldgebruik

### Weekplanning met budget
```
Plan boodschappen voor 4 dagen, 2 personen bij AH en Jumbo.
Budget max 80 euro, voorkeur voor pasta gerechten.
```

### Prijsalert instellen
```
Stel een alert in voor Douwe Egberts koffie onder 6 euro.
```

### Budget check
```
Check of melk, brood, kaas, eieren en boter binnen 15 euro budget past.
```

## Data Bronnen

- **Prijzen**: [Checkjebon.nl](https://checkjebon.nl) (dagelijks 06:00)
- **Aanbiedingen**: [Folderz.nl](https://folderz.nl) (2x per dag)
- **Recepten**: [TheMealDB](https://themealdb.com) + eigen NL recepten

## Automatische Sync (Cronjobs)

| Sync | Schema | Beschrijving |
|------|--------|--------------|
| Prijzen | 06:00 dagelijks | Producten van Checkjebon.nl |
| Folderz | 06:30 & 14:30 | Folder aanbiedingen |
| Recepten | Zondag 05:00 | Recepten database |

## Environment Variables

| Variable | Default | Beschrijving |
|----------|---------|--------------|
| DB_HOST | db | PostgreSQL host |
| DB_PORT | 5432 | PostgreSQL port |
| DB_NAME | supermarkt_db | Database naam |
| DB_USER | postgres | Database user |
| DB_PASSWORD | supermarkt123 | Database wachtwoord |

## Development

```bash
# Lokaal draaien (zonder Docker)
pip install -r requirements.txt
python src/server_sse.py

# Logs bekijken
docker logs supermarkt-mcp
docker logs supermarkt-scheduler
```

## License

MIT
