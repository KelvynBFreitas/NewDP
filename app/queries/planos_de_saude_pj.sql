SELECT
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
    -- Parte 1: RHCONTRATOSERVICOSCALC
    SELECT
      p.nome AS beneficiario,
      p.cpf,
      ecd.datatermino,
      NVL(t.custoempresa, 0) AS custoempresa,
      NVL(t.custofuncionario, 0) AS custofuncionario,
      NVL(t.custofuncionario, 0) AS VALOR_DESCONTA_NV,
      0 AS MT_NV
    FROM
      rhmeta.RHCONTRATOSERVICOSCALC t
      JOIN rhmeta.RHCONTRATOS tc ON t.unidade = tc.unidade
      AND t.contrato = tc.contrato
      JOIN rhmeta.rhpessoas p ON t.pessoa = p.pessoa
      AND t.empresa = p.empresa
      AND tc.pessoa = p.pessoa -- Garante a pessoa correta do contrato
      JOIN rhmeta.RHHISTCALCULOCONVENIOS ecd ON t.datahora = ecd.datahora
      JOIN rhmeta.rhempresas em ON tc.empresa = em.empresa
    WHERE
      t.convenio IN (2000, 3000, 6000, 0001, 7000)
      AND tc.situacao IN (1, 2)
      AND em.descricao20 IN ('Prestadores de servi')
      -- FILTRO MOVIDO PARA CÁ
      AND ecd.datainicio >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
      AND ecd.datatermino < ADD_MONTHS(TRUNC(SYSDATE, 'MM'), 1)
      
    UNION ALL
    
    -- Parte 2: RHCONTRATOPLANOSCALC
    SELECT
      p.nome AS beneficiario,
      p.cpf,
      ecd.datatermino,
      NVL(t.custoempresa, 0) AS custoempresa,
      NVL(t.custofuncionario, 0) AS custofuncionario,
      0 AS VALOR_DESCONTA_NV,
      CASE
        WHEN UPPER(ep.descricao40) LIKE ('%DENTAL%') THEN 0
        WHEN UPPER(ep.descricao40) LIKE ('%ORTOCLIN%') THEN 0
        ELSE NVL(t.custofuncionario, 0)
      END AS MT_NV
    FROM
      rhmeta.RHCONTRATOPLANOSCALC t
      JOIN rhmeta.rhplanosconvenios EP ON t.convenio = EP.convenio
      AND t.planomedico = EP.planomedico
      JOIN rhmeta.RHCONTRATOS tc ON t.unidade = tc.unidade
      AND t.contrato = tc.contrato
      JOIN rhmeta.rhpessoas p ON t.pessoa = p.pessoa
      AND t.empresa = p.empresa
      AND tc.pessoa = p.pessoa -- Garante a pessoa correta do contrato
      JOIN rhmeta.RHHISTCALCULOCONVENIOS ecd ON t.datahora = ecd.datahora
      JOIN rhmeta.rhempresas em ON tc.empresa = em.empresa
    WHERE
      t.convenio IN (2000, 3000, 6000, 0001, 7000)
      AND tc.situacao IN (1, 2)
      AND em.descricao20 IN ('Prestadores de servi')
      -- FILTRO MOVIDO PARA CÁ
      AND ecd.datainicio >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
      AND ecd.datatermino < ADD_MONTHS(TRUNC(SYSDATE, 'MM'), 1)
  ) benefi
GROUP BY
  BENEFICIARIO,
  cpf,
  datatermino