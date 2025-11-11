WITH
-- CTE 1: DADOS_FUNCIONARIOS (Materializado)
DADOS_FUNCIONARIOS AS (
    SELECT /*+ MATERIALIZE */
      RP.NOMECOMPLETO,
      RP.cpf,
      RU.DESCRICAO40 AS UNIDADE,
      E.DESCRICAO20 AS EMPRESA,
      R.SALARIOCONTRATUAL,
      RS.DESCRICAO40 AS SETOR,
      F.DESCRICAO40 AS FUNCAO,
      RB.DESCRICAO20 as ESTABELECIMENTO,
      R.ESTABELECIMENTOCONTRATA,
      case 
        when rp.cpf = '61946966304' then 'Sala CRM'
        else RCC.DESCRICAO40 
      end CLASSIFICACAO_CONTABIL,
      r.dataadmissao AS "DATAADMISSAO",
      rp.emailcorporativo as email_colaborador
    FROM RHMETA.RHCONTRATOS R
    JOIN RHMETA.RHPESSOAS RP ON R.PESSOA = RP.PESSOA AND R.EMPRESA = RP.EMPRESA
    JOIN RHMETA.RHUNIDADES RU ON R.UNIDADE = RU.UNIDADE
    JOIN RHMETA.RHEMPRESAS E ON R.EMPRESA = E.EMPRESA
    JOIN RHMETA.RHSETORES RS ON R.SETOR = RS.SETOR
    JOIN RHMETA.RHFUNCOES F ON R.FUNCAO = F.FUNCAO
    JOIN RHMETA.RHESTABELECIMENTOS RB ON R.ESTABELECIMENTO = RB.ESTABELECIMENTO
    JOIN RHMETA.RHCLASSCONTABEIS RCC ON R.CLASSIFICACAOCONTABIL = RCC.CLASSIFICACAOCONTABIL
    WHERE R.SITUACAO IN (1,2)
    AND E.DESCRICAO20 IN ('Prestadores de servi')
  --  and R.DATAADMISSAO >= TO_DATE('01/08/2025', 'DD/MM/YYYY')
    UNION ALL
    SELECT 
      'JULIO CESAR NUNES DE SOUSA', '67214673304', 'Prestadores de serviço', 'New House', 1, 'Veículos Novos',
      'Gerente comercial', 'New House ALD', '1104', 'Veículos Novos', TO_DATE('15/04/2024', 'DD/MM/YYYY'),
      'julio.nunes@gwmnewhouse.com.br'
    from dual
    UNION ALL
    SELECT 
      'JORGEANNE UCHOA DA SILVA MELO', '65293835300', 'Prestadores de serviço', 'New House', 1, 'Veículos Novos',
      'Gerente comercial', 'New House THE', '1102', 'Veículos Novos', TO_DATE('01/02/2024', 'DD/MM/YYYY'),
      'jorgeanne.melo@newlandjlr.com.br'
    from dual
),

-- CTE 2: DADOS_PLANOS_SAUDE (Materializado)
DADOS_PLANOS_SAUDE AS (
    SELECT /*+ MATERIALIZE */
      BENEFICIARIO,
      cpf, 
      SUM(custofuncionario) AS total_plano,
      datatermino,
      SUM(NVL(custoempresa, 0)) AS CUSTOEMPRESA,
      SUM(VALOR_DESCONTA_NV) AS VALOR_DESCONTA_NV,
      CASE
        WHEN SUM(MT_NV) > 1 THEN 'METODO_ANTIGO'
        WHEN SUM(NVL(custoempresa, 0)) = 0 AND SUM(MT_NV) < 1 THEN 'METODO_ANTIGO'
        ELSE 'METODO_NOVO'
      END METODO
    FROM
      (
        SELECT
          p.nome AS beneficiario, p.cpf, ecd.datatermino, NVL(t.custoempresa, 0) AS custoempresa,
          NVL(t.custofuncionario, 0) AS custofuncionario, NVL(t.custofuncionario, 0) AS VALOR_DESCONTA_NV, 0 AS MT_NV
        FROM rhmeta.RHCONTRATOSERVICOSCALC t
        JOIN rhmeta.RHCONTRATOS tc ON t.unidade = tc.unidade AND t.contrato = tc.contrato
        JOIN rhmeta.rhpessoas p ON t.pessoa = p.pessoa AND t.empresa = p.empresa AND tc.pessoa = p.pessoa
        JOIN rhmeta.RHHISTCALCULOCONVENIOS ecd ON t.datahora = ecd.datahora
        JOIN rhmeta.rhempresas em ON tc.empresa = em.empresa
        WHERE t.convenio IN (2000, 3000, 6000, 0001, 7000) AND tc.situacao IN (1, 2)
        AND em.descricao20 IN ('Prestadores de servi')
        AND ecd.datainicio >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
        AND ecd.datatermino < ADD_MONTHS(TRUNC(SYSDATE, 'MM'), 1)
        UNION ALL
        SELECT
          p.nome AS beneficiario, p.cpf, ecd.datatermino, NVL(t.custoempresa, 0) AS custoempresa,
          NVL(t.custofuncionario, 0) AS custofuncionario, 0 AS VALOR_DESCONTA_NV,
          CASE
            WHEN UPPER(ep.descricao40) LIKE ('%DENTAL%') THEN 0
            WHEN UPPER(ep.descricao40) LIKE ('%ORTOCLIN%') THEN 0
            ELSE NVL(t.custofuncionario, 0)
          END AS MT_NV
        FROM rhmeta.RHCONTRATOPLANOSCALC t
        JOIN rhmeta.rhplanosconvenios EP ON t.convenio = EP.convenio AND t.planomedico = EP.planomedico
        JOIN rhmeta.RHCONTRATOS tc ON t.unidade = tc.unidade AND t.contrato = tc.contrato
        JOIN rhmeta.rhpessoas p ON t.pessoa = p.pessoa AND t.empresa = p.empresa AND tc.pessoa = p.pessoa
        JOIN rhmeta.RHHISTCALCULOCONVENIOS ecd ON t.datahora = ecd.datahora
        JOIN rhmeta.rhempresas em ON tc.empresa = em.empresa
        WHERE t.convenio IN (2000, 3000, 6000, 0001, 7000) AND tc.situacao IN (1, 2)
        AND em.descricao20 IN ('Prestadores de servi')
        AND ecd.datainicio >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), 0)
        AND ecd.datatermino < ADD_MONTHS(TRUNC(SYSDATE, 'MM'), 1)
      ) benefi
    GROUP BY BENEFICIARIO, cpf, datatermino
),

-- CTEs 3.1: CALENDARIO (base para dias úteis)
Dias_No_Mes AS (
    SELECT TRUNC(SYSDATE, 'MM') + (LEVEL - 1) AS Dia
    FROM DUAL CONNECT BY LEVEL <= LAST_DAY(SYSDATE) - TRUNC(SYSDATE, 'MM') + 1
),
Dias_Uteis AS (
    SELECT Dia FROM Dias_No_Mes
    WHERE TO_CHAR(Dia, 'D', 'NLS_DATE_LANGUAGE=AMERICAN') NOT IN ('1', '7')
),
Feriados_Dias_Uteis AS (
    SELECT c.descricao40 AS Cidade, t.dataferiado, c.calendario
    FROM rhmeta.rhcalendarios c
    JOIN rhmeta.RHFERIADOS t ON c.calendario = t.calendario
    WHERE t.dataferiado >= TRUNC(SYSDATE, 'MM')
      AND t.dataferiado < TRUNC(ADD_MONTHS(SYSDATE, 1), 'MM')
      AND TO_CHAR(t.dataferiado, 'D', 'NLS_DATE_LANGUAGE=AMERICAN') NOT IN ('1', '7')
),

-- CTE 3.2: NOVO CTE para calcular o VALOR (Materializado)
-- Esta é a lógica da sua subquery correlacionada, agora executada apenas UMA VEZ.
CTE_VALOR_FINAL AS (
    SELECT /*+ MATERIALIZE */
        estabelecimento, calendario, valor
    FROM (
        SELECT
            VALE_ESTAB.estabelecimento,
            VALE_ESTAB.calendario,
            t1.valor,
            ROW_NUMBER() OVER (
                PARTITION BY VALE_ESTAB.estabelecimento, VALE_ESTAB.calendario 
                ORDER BY t1.dataultimoreajuste DESC
            ) as rn
        FROM
            rhmeta.RHVALORESVA t1
        JOIN
            rhmeta.rhvalesalimentacao c1 ON c1.valealimentacao = t1.valealimentacao
        JOIN
            (
                SELECT DISTINCT -- Adicionado DISTINCT para garantir 1 por estabelecimento
                    rd.valealimentacao,
                    es.calendario,
                    es.estabelecimento
                FROM
                    rhmeta.rhcontratosva rd
                JOIN
                    rhmeta.rhcontratosfolha c2 ON rd.unidade = c2.unidade AND rd.contrato = c2.contrato
                JOIN
                    rhmeta.rhestabelecimentos es ON c2.estabelecimento = es.estabelecimento
                WHERE
                    c2.datafolha >= TO_DATE('31/12/2024', 'DD/MM/YYYY')
                    AND rd.ativadesativada = 1
                    AND c2.situacao IN (1, 2)
            ) VALE_ESTAB ON VALE_ESTAB.valealimentacao = c1.valealimentacao
    )
    WHERE rn = 1
),

-- CTE 3.3: DADOS_VALOR_HORA_CIDADE (Agora mais simples)
DADOS_VALOR_HORA_CIDADE AS (
    SELECT
      c.descricao40 AS Cidade,
      empresas.estabelecimento_desc,
      empresas.calendario,
      empresas.estabelecimento,
      empresas.razaosocial,
      empresas.cidade AS cidade_empresa,
      TO_CHAR(TRUNC(SYSDATE, 'MM'), 'YYYY-MM') AS Mes,
      COUNT(DISTINCT d.Dia) AS Total_Dias_Uteis,
      COUNT(DISTINCT f.dataferiado) AS Total_Feriados_Uteis,
      (COUNT(DISTINCT d.Dia) - COUNT(DISTINCT f.dataferiado)) AS Dias_Uteis_Menos_Feriados,
      NVL(va.valor, 0) AS VALOR -- <--- MUDANÇA PRINCIPAL AQUI
    FROM
      rhmeta.rhcalendarios c
    CROSS JOIN
      Dias_Uteis d
    LEFT JOIN
      Feriados_Dias_Uteis f ON d.Dia = f.dataferiado AND c.calendario = f.calendario -- Join corrigido para calendario
    JOIN
      (
          SELECT e.calendario, e.estabelecimento, e.descricao20 AS estabelecimento_desc, e.razaosocial, t.descricao40 AS cidade
          FROM rhmeta.rhestabelecimentos e
          JOIN rhmeta.RHCALENDARIOS t ON e.calendario = t.calendario
      ) empresas ON empresas.calendario = c.calendario
    LEFT JOIN 
      CTE_VALOR_FINAL va ON empresas.estabelecimento = va.estabelecimento -- <--- MUDANÇA PRINCIPAL AQUI
                         AND empresas.calendario = va.calendario          -- <--- MUDANÇA PRINCIPAL AQUI
    GROUP BY
      c.descricao40,
      empresas.calendario,
      empresas.estabelecimento_desc,
      empresas.estabelecimento,
      empresas.razaosocial,
      empresas.cidade,
      NVL(va.valor, 0) -- Adicionado ao GROUP BY
)

-- QUERY FINAL: (Idêntica à sua)
SELECT 
    P.CPF,
    P.NOMECOMPLETO AS Nome,
    DVH.CIDADE,
    P.CLASSIFICACAO_CONTABIL AS centro,
    COALESCE(ROUND(PS.TOTAL_PLANO, 2), 0) AS planos,
    DVH.VALOR,
    DVH.calendario,
    ROUND((DVH.DIAS_UTEIS_MENOS_FERIADOS * DVH.VALOR) * 0.9, 2) AS vr,
    CASE 
        WHEN ROUND(((DVH.DIAS_UTEIS_MENOS_FERIADOS ) * DVH.VALOR) * 0.9, 2) - COALESCE(PS.TOTAL_PLANO, 0) <= 0 
        THEN 'Descontar na Nota >>>>>'
        ELSE 'Adicionar na Nota >>>>>' 
    END AS acao_,
    DVH.DIAS_UTEIS_MENOS_FERIADOS,
    ROUND(
        COALESCE((DVH.DIAS_UTEIS_MENOS_FERIADOS ) * DVH.VALOR * 0.9, 0) - COALESCE(PS.TOTAL_PLANO, 0), 
        2
    ) AS Resultado,
    NULL AS Motivo,
    P.dataadmissao AS dataadmissao,
    p.email_colaborador,
    NULL AS outros,
    case when ps.METODO = ('METODO_NOVO') then PS.CUSTOEMPRESA 
         else 0 
         end ressarcimento,
    ps.VALOR_DESCONTA_NV,
    ps.METODO
FROM 
    DADOS_FUNCIONARIOS P
JOIN 
    DADOS_VALOR_HORA_CIDADE DVH
    ON P.ESTABELECIMENTO = DVH.ESTABELECIMENTO_DESC
LEFT JOIN 
    DADOS_PLANOS_SAUDE PS 
    ON P.CPF = PS.CPF
GROUP BY 
    P.CPF, P.NOMECOMPLETO, DVH.CIDADE, P.CLASSIFICACAO_CONTABIL, PS.TOTAL_PLANO, 
    DVH.DIAS_UTEIS_MENOS_FERIADOS, DVH.VALOR, P.dataadmissao,DVH.calendario,p.email_colaborador,PS.CUSTOEMPRESA,
    ps.VALOR_DESCONTA_NV,ps.METODO
ORDER BY
    P.NOMECOMPLETO