-- Database schema for NL Supermarkt MCP

CREATE TABLE IF NOT EXISTS supermarkets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(10) DEFAULT '🏪'
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    supermarket_code VARCHAR(20) REFERENCES supermarkets(code),
    name VARCHAR(500) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    unit VARCHAR(100),
    link VARCHAR(1000),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supermarket_code, name)
);

CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    price DECIMAL(10,2) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS promotions (
    id SERIAL PRIMARY KEY,
    supermarket_code VARCHAR(20),
    product_name VARCHAR(500) NOT NULL,
    original_price DECIMAL(10,2),
    discount_price DECIMAL(10,2) NOT NULL,
    discount_percent INTEGER,
    promo_type VARCHAR(50),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supermarket_code, product_name, start_date)
);

CREATE TABLE IF NOT EXISTS recepten (
    id SERIAL PRIMARY KEY,
    naam VARCHAR(200) NOT NULL,
    categorie VARCHAR(50),
    bereidingstijd INTEGER,
    porties INTEGER,
    ingredienten JSONB,
    instructies JSONB,
    tags JSONB,
    bron VARCHAR(100),
    external_id VARCHAR(50),
    afbeelding VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(naam, bron)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_supermarket ON products(supermarket_code);
CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_promotions_supermarket ON promotions(supermarket_code);
CREATE INDEX IF NOT EXISTS idx_promotions_end_date ON promotions(end_date);

-- Enable trigram extension for fuzzy search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Insert default supermarkets
INSERT INTO supermarkets (code, name, icon) VALUES
    ('ah', 'Albert Heijn', '🟦'),
    ('jumbo', 'Jumbo', '🟨'),
    ('aldi', 'Aldi', '🟧'),
    ('lidl', 'Lidl', '🟦'),
    ('plus', 'Plus', '🟩'),
    ('dekamarkt', 'DekaMarkt', '🟥'),
    ('vomar', 'Vomar', '🟧'),
    ('dirk', 'Dirk', '🟥'),
    ('coop', 'Coop', '🟩'),
    ('hoogvliet', 'Hoogvliet', '🟧'),
    ('spar', 'Spar', '🟩'),
    ('picnic', 'Picnic', '🟨'),
    ('nettorama', 'Nettorama', '🟧'),
    ('poiesz', 'Poiesz', '🟩'),
    ('janlinders', 'Jan Linders', '🟥'),
    ('boni', 'Boni', '🟨')
ON CONFLICT (code) DO NOTHING;

-- ============================================
-- NIEUWE TABELLEN VOOR UITGEBREIDE FEATURES
-- ============================================

-- Opgeslagen boodschappenlijsten
CREATE TABLE IF NOT EXISTS shopping_lists (
    id SERIAL PRIMARY KEY,
    naam VARCHAR(100) NOT NULL,
    items JSONB NOT NULL,
    totaal DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gebruikersvoorkeuren en alerts
CREATE TABLE IF NOT EXISTS product_alerts (
    id SERIAL PRIMARY KEY,
    product_query VARCHAR(200) NOT NULL,
    max_prijs DECIMAL(10,2),
    notify_on_sale BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Supermarkt locaties
CREATE TABLE IF NOT EXISTS supermarket_locations (
    id SERIAL PRIMARY KEY,
    supermarket_code VARCHAR(20) REFERENCES supermarkets(code),
    naam VARCHAR(200),
    adres VARCHAR(300),
    postcode VARCHAR(10),
    stad VARCHAR(100),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    openingstijden JSONB
);

-- Budget tracking
CREATE TABLE IF NOT EXISTS budget_history (
    id SERIAL PRIMARY KEY,
    weeknummer INTEGER,
    jaar INTEGER,
    budget DECIMAL(10,2),
    uitgegeven DECIMAL(10,2),
    bespaard DECIMAL(10,2),
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index voor prijshistorie
CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(product_id);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(recorded_at);
