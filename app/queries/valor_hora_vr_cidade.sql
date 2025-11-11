WITH Dias_No_Mes AS (
    SELECT
        TRUNC(SYSDATE, 'MM') + (LEVEL - 1) AS Dia
    FROM
        DUAL
    CONNECT BY
        LEVEL <= LAST_DAY(SYSDATE) - TRUNC(SYSDATE, 'MM') + 1
),
Dias_Uteis AS (
    SELECT
        Dia
    FROM
        Dias_No_Mes
    WHERE
        TO_CHAR(Dia, 'D', 'NLS_DATE_LANGUAGE=AMERICAN') NOT IN ('1', '7') -- Exclui domingos e sábados
),
Feriados_Dias_Uteis AS (
    SELECT
        c.descricao40 AS Cidade,
        t.dataferiado
    FROM
        rhmeta.rhcalendarios c
    JOIN
        rhmeta.RHFERIADOS t
        ON c.calendario = t.calendario
    WHERE
        t.dataferiado >= TRUNC(SYSDATE, 'MM')
        AND t.dataferiado < TRUNC(ADD_MONTHS(SYSDATE, 1), 'MM')
        AND TO_CHAR(t.dataferiado, 'D', 'NLS_DATE_LANGUAGE=AMERICAN') NOT IN ('1', '7') -- Exclui domingos e sábados
)
SELECT
    c.descricao40 AS Cidade,
    empresas.estabelecimento_desc,
    empresas.calendario,
    empresas.estabelecimento,
    empresas.razaosocial,
    empresas.cidade,
    TO_CHAR(TRUNC(SYSDATE, 'MM'), 'YYYY-MM') AS Mes,
    COUNT(DISTINCT d.Dia) AS Total_Dias_Uteis,
    COUNT(DISTINCT f.dataferiado) AS Total_Feriados_Uteis,
    COUNT(DISTINCT d.Dia) - COUNT(DISTINCT f.dataferiado) AS Dias_Uteis_Menos_Feriados,
    (
        select
nvl(valor.valor,0) valor
from (

SELECT
    t1.dataultimoreajuste, t1.valor,t1.valealimentacao
FROM
    rhmeta.RHVALORESVA t1
JOIN
    rhmeta.rhvalesalimentacao c1
    ON c1.valealimentacao = t1.valealimentacao
JOIN
    (
        SELECT
            rd.valealimentacao,
            es.descricao20,
            es.calendario,
            es.descricao20 AS empresas,
            es.estabelecimento
        FROM
            rhmeta.rhcontratosva rd
        JOIN
            rhmeta.rhcontratosfolha c2
            ON rd.unidade = c2.unidade
            AND rd.contrato = c2.contrato
        JOIN
            rhmeta.rhestabelecimentos es
            ON c2.estabelecimento = es.estabelecimento
            AND c2.datafolha >= TO_DATE('31/12/2024', 'DD/MM/YYYY')
        WHERE
            rd.ativadesativada = 1
            AND c2.situacao IN (1, 2)
    ) VALE_ESTAB
    ON VALE_ESTAB.valealimentacao = c1.valealimentacao
WHERE
     empresas.estabelecimento = VALE_ESTAB.estabelecimento
        AND empresas.calendario = VALE_ESTAB.calendario
        and t1.valealimentacao = VALE_ESTAB.valealimentacao
ORDER BY
    t1.dataultimoreajuste  DESC
FETCH FIRST 1 ROWS ONLY
)valor
          ) AS VALOR
FROM
    rhmeta.rhcalendarios c
CROSS JOIN
    Dias_Uteis d
LEFT JOIN
    Feriados_Dias_Uteis f
    ON d.Dia = f.dataferiado AND c.descricao40 = f.Cidade
JOIN
    (
        SELECT
            e.calendario,
            e.estabelecimento,
            e.descricao20 AS estabelecimento_desc,
            e.razaosocial,
            t.descricao40 AS cidade
        FROM
            rhmeta.rhestabelecimentos e
        JOIN
            rhmeta.RHCALENDARIOS t
        ON
            e.calendario = t.calendario
    ) empresas
    ON empresas.calendario = c.calendario
GROUP BY
    c.descricao40,
    empresas.calendario,
    empresas.estabelecimento_desc,
    empresas.estabelecimento,
    empresas.razaosocial,
    empresas.cidade
ORDER BY
    c.descricao40, Mes