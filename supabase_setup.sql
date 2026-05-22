-- Ejecutar en Supabase → SQL Editor → Run
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS usuarios (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         TEXT UNIQUE NOT NULL,
    nombre        TEXT,
    es_nuevo      BOOLEAN DEFAULT TRUE,
    creado_en     TIMESTAMPTZ DEFAULT NOW(),
    ultima_sesion TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversaciones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_usuario   TEXT NOT NULL REFERENCES usuarios(email) ON DELETE CASCADE,
    mensajes        JSONB DEFAULT '[]'::jsonb,
    actualizado_en  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_email ON conversaciones(email_usuario);

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN NEW.actualizado_en = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_conv
    BEFORE UPDATE ON conversaciones
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

SELECT 'Tablas creadas correctamente' AS status;
