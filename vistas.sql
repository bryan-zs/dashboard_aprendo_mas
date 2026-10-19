-- CREACIÓN DE VISTAS

-- Se indica que una persona cuenta una sola vez aunque tenga más de un registro.
-- Se considera utilizar la primera `fecha_alta` de cada `telefono_hash` para deduplicar registros de familias.
CREATE OR REPLACE VIEW v_familias AS
SELECT
    p.telefono_hash,
    FIRST(it.ugel) AS ugel,
    FIRST(it.institucion_id) AS institucion_id,
    FIRST(it.zona) AS zona,
    FIRST(p.grupo_id) AS grupo_id,
    MIN(CAST(p.fecha_alta AS DATE)) AS fecha_alta,
    DATE_TRUNC('week', MIN(p.fecha_alta)::DATE) + INTERVAL 6 DAY AS fin_de_semana -- Calculo el fin de semana según la fecha alta
FROM db.participantes p
JOIN db.grupos g
ON g.grupo_id = p.grupo_id
JOIN db.instituciones it
ON it.institucion_id = g.institucion_id
WHERE p.rol = 'familia'
GROUP BY p.telefono_hash; -- 1023 filas = 1101 (originales) - 48 (docentes) -  30 (telefonos duplicados)

-- Interacciones válidas en hora Lima, con el tipo normalizado y la semana de su actividad.
CREATE OR REPLACE VIEW v_evidencias AS
SELECT
    f.telefono_hash,
    f.ugel,
    f.institucion_id,
    f.zona,
    f.grupo_id,
    i.actividad_id,
    CAST(a.fecha_envio_utc AS TIMESTAMP) - INTERVAL 5 HOUR AS fecha_envio, -- convierto a hora peruana
    a.semana,
    CAST(i.fecha_hora_utc AS TIMESTAMP) - INTERVAL 5 HOUR AS fecha_evidencia, -- convierto a hora peruana
    LOWER(TRIM(i.tipo)) AS tipo,
    DATE_TRUNC('week', (i.fecha_hora_utc::TIMESTAMP - INTERVAL 5 HOUR)::DATE) + INTERVAL 6 DAY AS fin_de_semana,
FROM db.interacciones i
JOIN db.actividades a
ON a.actividad_id = i.actividad_id
JOIN db.participantes p
ON p.participante_id = i.participante_id AND p.rol = 'familia' -- ningún docente envía evidencias, entonces filtro por familia
JOIN v_familias f
ON f.telefono_hash = p.telefono_hash -- vinculo mediante telefono_hash para evitar familias duplicadas
WHERE
    i.fecha_hora_utc::TIMESTAMP - INTERVAL 5 HOUR > a.fecha_envio_utc::TIMESTAMP - INTERVAL 5 HOUR -- valido que las evidencias se envien luego del envío de la actividad
    AND LOWER(TRIM(i.tipo)) in ('foto', 'imagen', 'audio', 'video'); -- 3275 filas

-- calculo de las evidencias por grupo por semana
CREATE OR REPLACE VIEW v_evidencias_semanales AS
WITH evidencias_enviadas AS (
    SELECT
        semana,
        fin_de_semana,
        ugel,
        institucion_id,
        zona,
        grupo_id,
        COUNT(DISTINCT telefono_hash) as evidencias,
    FROM v_evidencias
    GROUP BY semana, fin_de_semana, ugel, institucion_id, zona, grupo_id
    ORDER BY semana, fin_de_semana, ugel, grupo_id
), -- 287 registros, deberían ser 288 = 48 grupos x 6 semanas

grilla AS (
    SELECT
        v_e_s.semana,
        v_e_s.fin_de_semana,
        u_g.ugel,
        u_g.institucion_id,
        u_g.zona,
        u_g.grupo_id,
    FROM (
        SELECT
            semana,
            FIRST(fin_de_semana) AS fin_de_semana
        FROM evidencias_enviadas
        GROUP BY semana
    ) v_e_s
    CROSS JOIN (
        SELECT
            it.ugel,
            it.institucion_id,
            it.zona,
            g.grupo_id
        FROM db.grupos g
        JOIN db.instituciones it
        ON g.institucion_id = it.institucion_id
    ) u_g
) -- 288 registros, se usa para imputar los grupo x semana sin evidencias enviadas

SELECT
    COALESCE(e.semana, g.semana) AS semana,
    COALESCE(e.fin_de_semana, g.fin_de_semana) AS fin_de_semana,
    COALESCE(e.ugel, g.ugel) AS ugel,
    COALESCE(e.institucion_id, g.institucion_id) AS institucion_id,
    COALESCE(e.zona, g.zona) AS zona,
    COALESCE(e.grupo_id, g.grupo_id) AS grupo_id,
    COALESCE(e.evidencias, 0) AS evidencias,
FROM evidencias_enviadas e
FULL JOIN grilla g
ON e.semana = g.semana AND e.ugel = g.ugel AND e.grupo_id = g.grupo_id
ORDER BY semana, ugel, grupo_id; -- 288 registros completos sin nulos

-- Vista de evidencias por grupo por semana con la cantidad de familiares registrados hasta la fecha
CREATE OR REPLACE VIEW v_grupo_semana AS
WITH familias_agrupadas AS (
    SELECT
        fin_de_semana,
        ugel,
        institucion_id,
        zona,
        grupo_id,
        COUNT(*) as registradas, -- cuento las familias registradas por semana
    FROM v_familias
    GROUP BY fin_de_semana, ugel, institucion_id, zona, grupo_id
    ORDER BY fin_de_semana, ugel, grupo_id
),

registros_semanales AS (
    SELECT
        fin_de_semana,
        ugel,
        institucion_id,
        zona,
        grupo_id,
        registradas,
        SUM(registradas) OVER (
            PARTITION BY ugel, grupo_id
            ORDER BY fin_de_semana
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS registradas_acumuladas -- calculo la suma acumulada de familias registradas hasta cada fin de semana
    FROM familias_agrupadas
    ORDER BY fin_de_semana, ugel, grupo_id
),

evidencias_registros AS (
    SELECT
        e_s.semana,
        COALESCE(e_s.fin_de_semana, r_s.fin_de_semana) AS fin_de_semana,
        COALESCE(e_s.ugel, r_s.ugel) AS ugel,
        COALESCE(e_s.institucion_id, r_s.institucion_id) AS institucion_id,
        COALESCE(e_s.zona, r_s.zona) AS zona,
        COALESCE(e_s.grupo_id, r_s.grupo_id) AS grupo_id,
        e_s.evidencias,
        r_s.registradas_acumuladas
    FROM v_evidencias_semanales e_s
    FULL JOIN registros_semanales r_s
    ON e_s.ugel = r_s.ugel AND e_s.grupo_id = r_s.grupo_id AND e_s.fin_de_semana = r_s.fin_de_semana -- unifico las evidencias con las familias registradas
    ORDER BY fin_de_semana, ugel, grupo_id
),

imputado AS (
    SELECT
        * EXCLUDE registradas_acumuladas,
        LAST_VALUE(registradas_acumuladas IGNORE NULLS) OVER (
            PARTITION BY ugel, grupo_id
            ORDER BY fin_de_semana
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )::INT AS registradas -- imputo los nulos con un feed fodward
    FROM evidencias_registros
)

SELECT
    * 
FROM imputado
WHERE semana IS NOT NULL -- filtro solo las 6 semanas del análisis
ORDER BY fin_de_semana, ugel, grupo_id;

CREATE OR REPLACE VIEW v_abandonan AS
SELECT f.telefono_hash, f.grupo_id, f.ugel, f.zona,
FROM v_familias f
WHERE (SELECT COUNT(DISTINCT e.semana) FROM v_evidencias e
       WHERE e.telefono_hash = f.telefono_hash AND e.semana BETWEEN 1 AND 4) >= 2 -- evidencia en +2 de las primeras 4 semanas 
  AND NOT EXISTS (SELECT 1 FROM v_evidencias e
                  WHERE e.telefono_hash = f.telefono_hash AND e.semana IN (5, 6)); -- sin evidencia en las últimas 2 semanas
