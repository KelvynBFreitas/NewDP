import pandas as pd
from datetime import datetime

def format_currency(value):
    """
    Formata valores float/string para moeda BRL (R$ 1.234,56)
    """
    try:
        if pd.isna(value) or value == '' or value is None:
            return "R$ 0,00"
        
        # Converte para float se for string numérica
        val_float = float(value)
        
        # Formatação brasileira manual (troca ponto por virgula e vice-versa)
        return f"R$ {val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(value)

def gerar_html_para_email_aprovador(lista_dados, mock_vars):
    """
    Gera o HTML completo do e-mail para um aprovador específico.
    """
    # 1. Cria DataFrame a partir da lista de dicionários
    df = pd.DataFrame(lista_dados)

    # 2. Mapeamento das colunas (Banco de Dados -> Nome no E-mail)
    colunas_desejadas = {
        'nome': 'Nome Completo',
        'razao_social': 'Razão Social',
        'centro_de_custo': 'Centro de Custo',
        'aprovador': 'Aprovador',
        'desconto_plano': 'Desconto Plano',
        'vr': 'Valor de Refeição',
        'ressarcimento': 'Ressarcimento',
        'outros': 'Outros Valores',
        'acao': 'Ação', # Encurtei um pouco para caber na tabela
        'resultado': 'Valor Final'
    }
    
    # 3. Filtra apenas colunas existentes para evitar erros se o banco mudar
    cols_existentes = [c for c in colunas_desejadas.keys() if c in df.columns]
    df_final = df[cols_existentes].copy()

    # 4. Formatação de Moeda
    # Lista de colunas que são valores monetários
    # Verifica se todos os valores da coluna 'outros' são 0.0
    if df_final['outros'].eq(0.0).all():
        df_final = df_final.drop(columns=['outros'])
    else:
        #df_selecionado['Outros Valores'] = df_selecionado['Outros Valores'].astype(str)
        df_final['outros'] = df_final['outros']
    # Converte para número (coercivamente, tratando erros como NaN)
    df_final['ressarcimento'] = pd.to_numeric(df_final['ressarcimento'], errors='coerce')

    # Verifica se algum valor é maior que 0
    if df_final['ressarcimento'].eq(0.0).all():
        df_final = df_final.drop(columns=['ressarcimento'])
    else:
        df_final['ressarcimento'] = df_final['ressarcimento']
        
    
    colunas_financeiras = ['desconto_plano', 'vr', 'ressarcimento', 'outros', 'resultado']
    
    for col in colunas_financeiras:
        if col in df_final.columns:
            # Preenche vazio com 0 e aplica formatação
            df_final[col] = df_final[col].fillna(0).apply(format_currency)

    # 5. Renomeia as colunas para o cabeçalho da tabela
    df_final = df_final.rename(columns=colunas_desejadas)

    # 6. Gera a Tabela HTML
    tabela_html = df_final.to_html(
        index=False, 
        classes='styled-table', 
        border=0, 
        justify='left', 
        escape=False # Permite HTML dentro das células se necessário
    )

    # 7. Recupera nome do Aprovador para saudação (pega da primeira linha)
    nome_aprovador_display = "Gestor"
    if 'Aprovador' in df_final.columns and not df_final.empty:
        val = df_final.iloc[0]['Aprovador']
        if val and isinstance(val, str):
            nome_aprovador_display = val.split(" ")[0].title()

    # 8. Definição do CSS (Estilo Grupo Newland)
    estilos_css = """
    <style>
        body {
            margin: 0; padding: 0; width: 100% !important;
            background-color: #f0f2f5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #333333;
        }

        /* Wrapper sempre 100% no celular */
        .wrapper {
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 auto;
            border-radius: 8px;
            background-color: #ffffff;
            border: 1px solid #dbe1e6;
        }

        .banner { padding: 30px 40px; border-bottom: 1px solid #eaeaea; }
        .banner-logo img { max-height: 40px; width: auto; }
        .banner-title-block { text-align: right; }
        .banner-title-block h1 { margin: 0; font-size: 22px; font-weight: 700; color: #111; }
        .subtitle-box {
            background-color: #fde047; color: #1f2937;
            padding: 5px 12px; display: inline-block;
            font-weight: 600; font-size: 14px; border-radius: 6px; margin-top: 8px;
        }

        .content-box {
            background-color: #fffefb;
            border: 2px solid #fde047;
            border-radius: 8px;
            padding: 25px 25px; /* padding reduzido no mobile */
            margin: 0 20px 30px;
        }

        .content-box p { font-size: 16px; line-height: 1.6; color: #374151; margin-bottom: 1.5em; }
        .greeting { font-size: 20px; font-weight: 600; color: #111; margin-bottom: 1em; }
        h3.section-title { font-size: 18px; font-weight: 700; color: #111; margin-top: 25px; margin-bottom: 15px; }

        .dates-box {
            background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;
            padding: 18px; margin: 20px 0; color: #333;
        }

        .dates-box-title { font-weight: 600; font-size: 16px; margin-bottom: 10px; }

        .info-box {
            background-color: #f3f4f6; border-left: 5px solid #ef4444;
            padding: 16px 20px; margin: 20px 0; font-size: 15px; color: #333;
            border-radius: 0 4px 4px 0;
        }

        /* 🔥 CORREÇÃO PRINCIPAL – QUEBRAR TEXTO NO MOBILE */
        .styled-table {
            width: 100%;
            max-width: 100%;
            min-width: 1200px;
            border-collapse: collapse;
            font-size: 12px;
            border: 1px solid #e5e7eb;
        }

        .styled-table th {
            background-color: #222;
            color: #fff;
            padding: 10px;
            text-align: left;
            font-weight: 600;

            /* antes era nowrap – CAUSAVA O BUG NO CELULAR */
            white-space: normal !important;
            word-break: break-word !important;
        }

        .styled-table td {
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
            background-color: #fff;

            white-space: normal !important;
            word-break: break-word !important;
        }

        .styled-table tr:nth-of-type(even) td { background-color: #f9f9f9; }

        .footer-block { background-color: #ffffff; padding: 0 20px 30px; }

        .video-box {
            text-align: center;
            background-color: #ffffff;
            border: 1px dashed #cccccc;
            padding: 20px;
            border-radius: 8px;
            margin-top: 25px;
        }

        .btn-video {
            display: inline-block;
            background-color: #d93025;
            color: #ffffff !important;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 14px;
            margin-top: 10px;
        }

        /* 🔥 Ajustes específicos para telas pequenas */
        @media (max-width: 1200px) {

            .banner {
                padding: 20px 20px;
            }

            .banner-title-block {
                text-align: left !important;
                margin-top: 10px;
            }

            .content-box {
                margin: 0 10px 20px;
                padding: 20px;
            }

            .styled-table th,
            .styled-table td {
                font-size: 11px !important;
                padding: 8px !important;
            }

            .btn-video {
                width: 100%;
            }
        }
    </style>
    """

    # 9. Montagem do HTML Final
    corpo_email = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gratificação Anual</title>
        {estilos_css}
    </head>
    <body>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f0f2f5;">
            <tr>
                <td align="center" style="padding: 20px 0;">
                    <table class="wrapper" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td>
                                <table class="banner" width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td class="banner-logo" width="50%">
                                            <img src="https://www.grupo-new.com/logos/_img/0.png" alt="Logo Empresa">
                                        </td>
                                        <td class="banner-title-block" width="50%">
                                            <h1>INFORMAÇÃO IMPORTANTE</h1>
                                            <span class="subtitle-box">{mock_vars.get('referencia_holmes')}</span>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <tr>
                            <td>
                                <div class="content-box">
                                    <p class="greeting">Olá,{nome_aprovador_display}, tudo bem?</p>
                                    <p>Como já é do conhecimento de todos, a autorização de um gestor direto é necessária para prestadores
                                      de serviços que possuem valores variáveis em suas Notas Fiscais (comissão, gratificação e premiação) 
                                      a fim de seguirmos com o fluxo de pagamento via Holmes. Referente à: <strong>1ª Parcela da Gratificação Anual 2025</strong>.</p>
                                    <h3 class="section-title">🗓️&nbsp;&nbsp;Datas Importantes</h3>
                                    <div class="dates-box">
                                        <p class="dates-box-title">Atenção aos Prazos:</p>
                                        <ul>
                                             <li><strong>Emissão e Envio (Holmes): </strong>{mock_vars.get('quinto_dia')} ({mock_vars.get('dia_semana')}), às 18:00.</li>
                                            <li><strong>Pagamento Programado: </strong> {mock_vars.get('primeiro_dia')} ({mock_vars.get('dia_semana_e')}).</li>
                                        </ul>
                                        <p style="margin: 12px 0 0 0; font-size: 14px; color: #666;">
                                            <em>Obs: Processos aprovados após o prazo poderão ter o pagamento reagendado conforme os prazos do Holmes.
                                              Em caso de dúvidas ou dificuldades com o acesso ao Holmes, entre em contato com o Escritório de Processos para suporte.</em>
                                        </p>
                                    </div>
                                    
                                    <h3 class="section-title">🧾&nbsp;&nbsp;Dados para Conferência</h3>
                                    {tabela_html}

                                    <h3 class="section-title">⚠️&nbsp;&nbsp;Orientações</h3>
                                    
                                    <div class="info-box">
                                        <strong>Pontos de Atenção:</strong><br><br>
                                        1. Verifique os processos pendentes atribuídos à sua aprovação.<br>
                                        2. Certifique-se de que todas as informações estão corretas antes de aprovar.
                                    </div>

                                    

                                    
                                    <p style="margin-top: 30px;">
                                        Atenciosamente,<br>
                                        <strong>Departamento Pessoal</strong>
                                    </p>
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td class="footer-block">
                                <table style="font-family: Arial, sans-serif; font-size: 12px;" cellpadding="10" cellspacing="0" border="0">
                                 <tbody><tr>
                                   <td style="font-size: 18px; color: rgb(0, 0, 0);" class="AssNome">Silmara Silva</td>
                                   <td style="text-align: left;"><img src="https://www.grupo-new.com/logos/_img/0.png" border="0" style="max-width: 300px; height: auto; max-height: 100px;" id="imgFlag" width="200"></td>
                                 </tr>
                                 <tr style="background: #ebebeb; color:#000;">
                                   <td valign="top">
                                     <b class="AssSetor">Gerente DP</b><br>
                                     <span class="AssTelefone">(85) 4005-1427</span><br>
                                     <a href="mailto:silmara.silva@gruponewland.com.br" style="color:#000; text-decoration: none;" class="AssEmail">silmara.silva@gruponewland.com.br</a>
                                   </td>
                                   <td style="text-align: right; padding-left: 10px;" class="logoGrupo" valign="top"></td>
                                 </tr>
                                 <tr style="background: rgb(0, 0, 0); color: rgb(255, 255, 255);" class="rodape">
                                   <td colspan="2" class="AssEndereco">Av. Washington Soares, 1550 • Fortaleza / Ceará / Brasil</td>
                                 </tr>
                               </tbody></table>
                                
                               <p style="font-size:10px; color:#666; font-family: Arial">Esta mensagem pode conter informação
              confidencial ou privilegiada, sendo seu sigilo protegido por lei. Se você não for o
              destinatário ou a pessoa autorizada a receber esta mensagem, não pode usar, copiar ou divulgar as
              informações nela contidas ou tomar qualquer ação baseada nessas
              informações. Se você recebeu esta mensagem por engano, por favor, avise imediatamente ao
              remetente, respondendo o e-mail e em seguida apague-a. Agradecemos sua cooperação.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return corpo_email

def gerar_html_para_email_colaborador(dados_row, mock_vars):
    """
    Gera o HTML individual para o COLABORADOR.
    Agora usa as MESMAS colunas que o gestor.
    """
    # Cria DataFrame com uma linha só
    df = pd.DataFrame([dados_row])

    # 1. Definição das Colunas (EXATAMENTE IGUAIS AO GESTOR)
    colunas_desejadas = {
        'nome': 'Nome Completo',
        'razao_social': 'Razão Social',
        'centro_de_custo': 'Centro de Custo',
        'aprovador': 'Aprovador', # Mantido, pois o colaborador pode querer saber quem aprova
        'desconto_plano': 'Desconto Plano',
        'vr': 'Valor de Refeição',
        'ressarcimento': 'Ressarcimento',
        'outros': 'Outros Valores',
        'acao': 'Ação',
        'resultado': 'Valor Final'
    }
    
    # 2. Filtra colunas existentes
    cols_existentes = [c for c in colunas_desejadas.keys() if c in df.columns]
    df_final = df[cols_existentes].copy()

    if df_final['outros'].eq(0.0).all():
        df_final = df_final.drop(columns=['outros'])
    else:
        #df_selecionado['Outros Valores'] = df_selecionado['Outros Valores'].astype(str)
        df_final['outros'] = df_final['outros']
    # Converte para número (coercivamente, tratando erros como NaN)
    df_final['ressarcimento'] = pd.to_numeric(df_final['ressarcimento'], errors='coerce')

    # Verifica se algum valor é maior que 0
    if df_final['ressarcimento'].eq(0.0).all():
        df_final = df_final.drop(columns=['ressarcimento'])
    else:
        df_final['ressarcimento'] = df_final['ressarcimento']
        
    if df_final['aprovador'].isna().all() or df_final['aprovador'].eq('').all():
        df_final = df_final.drop(columns=['aprovador'])
        cabechalhoa =""" """
    else:
        val1 = df_final.iloc[0]['aprovador']
        aprovador = val1.title()
        cabechalhoa = f"""
            <p>
            Em caso de variação do valor fixo da prestação de serviço (comissão, gratificação e premiação), 
            indicar "Sim" no campo "variação do valor fixo" ao abrir processo no Holmes. 
            Seu processo deve ser direcionado para validação da sua gestão direta: <strong>{aprovador}</strong>
        </p>
        """
    # 3. Formatação de Moeda (Mesmas colunas financeiras)
    colunas_financeiras = ['desconto_plano', 'vr', 'ressarcimento', 'outros', 'resultado']
    for col in colunas_financeiras:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna(0).apply(format_currency)

    # 4. Renomeia
    df_final = df_final.rename(columns=colunas_desejadas)
    
    # 5. Gera Tabela
    tabela_html = df_final.to_html(index=False, classes='styled-table', border=0, justify='left', escape=False)

    # Extração do Nome para a Saudação (adaptado para a nova coluna 'Nome Completo')
    nome_colaborador = "Colaborador"
    if 'Nome Completo' in df_final.columns and not df_final.empty:
        val = df_final.iloc[0]['Nome Completo']
        if val and isinstance(val, str):
            nome_colaborador = val.split(" ")[0].title()

    # --- ESTILOS CSS (Reutilizando o estilo padrão) ---
    estilos_css_layout_novo = """
       <style>
        body {
            margin: 0; padding: 0; width: 100% !important;
            background-color: #f0f2f5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #333333;
        }

        /* Wrapper sempre 100% no celular */
        .wrapper {
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 auto;
            border-radius: 8px;
            background-color: #ffffff;
            border: 1px solid #dbe1e6;
        }

        .banner { padding: 30px 40px; border-bottom: 1px solid #eaeaea; }
        .banner-logo img { max-height: 40px; width: auto; }
        .banner-title-block { text-align: right; }
        .banner-title-block h1 { margin: 0; font-size: 22px; font-weight: 700; color: #111; }
        .subtitle-box {
            background-color: #fde047; color: #1f2937;
            padding: 5px 12px; display: inline-block;
            font-weight: 600; font-size: 14px; border-radius: 6px; margin-top: 8px;
        }

        .content-box {
            background-color: #fffefb;
            border: 2px solid #fde047;
            border-radius: 8px;
            padding: 25px 25px; /* padding reduzido no mobile */
            margin: 0 20px 30px;
        }

        .content-box p { font-size: 16px; line-height: 1.6; color: #374151; margin-bottom: 1.5em; }
        .greeting { font-size: 20px; font-weight: 600; color: #111; margin-bottom: 1em; }
        h3.section-title { font-size: 18px; font-weight: 700; color: #111; margin-top: 25px; margin-bottom: 15px; }

        .dates-box {
            background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;
            padding: 18px; margin: 20px 0; color: #333;
        }

        .dates-box-title { font-weight: 600; font-size: 16px; margin-bottom: 10px; }

        .info-box {
            background-color: #f3f4f6; border-left: 5px solid #ef4444;
            padding: 16px 20px; margin: 20px 0; font-size: 15px; color: #333;
            border-radius: 0 4px 4px 0;
        }

        /* 🔥 CORREÇÃO PRINCIPAL – QUEBRAR TEXTO NO MOBILE */
        .styled-table {
            width: 100%;
            max-width: 100%;
            min-width: 1200px;
            border-collapse: collapse;
            font-size: 12px;
            border: 1px solid #e5e7eb;
        }

        .styled-table th {
            background-color: #222;
            color: #fff;
            padding: 10px;
            text-align: left;
            font-weight: 600;

            /* antes era nowrap – CAUSAVA O BUG NO CELULAR */
            white-space: normal !important;
            word-break: break-word !important;
        }

        .styled-table td {
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
            background-color: #fff;

            white-space: normal !important;
            word-break: break-word !important;
        }

        .styled-table tr:nth-of-type(even) td { background-color: #f9f9f9; }

        .footer-block { background-color: #ffffff; padding: 0 20px 30px; }

        .video-box {
            text-align: center;
            background-color: #ffffff;
            border: 1px dashed #cccccc;
            padding: 20px;
            border-radius: 8px;
            margin-top: 25px;
        }

        .btn-video {
            display: inline-block;
            background-color: #d93025;
            color: #ffffff !important;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 50px;
            font-weight: bold;
            font-size: 14px;
            margin-top: 10px;
        }

        /* 🔥 Ajustes específicos para telas pequenas */
        @media (max-width: 1200px) {

            .banner {
                padding: 20px 20px;
            }

            .banner-title-block {
                text-align: left !important;
                margin-top: 10px;
            }

            .content-box {
                margin: 0 10px 20px;
                padding: 20px;
            }

            .styled-table th,
            .styled-table td {
                font-size: 11px !important;
                padding: 8px !important;
            }

            .btn-video {
                width: 100%;
            }
        }
    </style>

    """

    corpo_email = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Gratificação Anual</title>
        {estilos_css_layout_novo}
    </head>
    <body>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f0f2f5;">
            <tr>
                <td align="center" style="padding: 20px 0;">
                    <table class="wrapper" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td>
                                <table class="banner" width="100%" cellpadding="0" cellspacing="0" border="0">
                                    <tr>
                                        <td class="banner-logo" width="50%">
                                            <img src="https://www.grupo-new.com/logos/_img/0.png" alt="Logo Empresa">
                                        </td>
                                        <td class="banner-title-block" width="50%">
                                            <h1>INFORMAÇÃO IMPORTANTE</h1>
                                            <span class="subtitle-box">{mock_vars.get('mes_ano_ref')}</span>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <tr>
                            <td>
                                <div class="content-box">
                                    <p class="greeting">Olá, {nome_colaborador}, tudo bem?</p>
                                    <p>Seguem as informações para emissão de sua Nota Fiscal referente à <strong>{mock_vars.get('referencia_holmes')}</strong>.</p>

                                    <h3 class="section-title">🗓️&nbsp;&nbsp;Datas Importantes</h3>
                                    <div class="dates-box">
                                        <p class="dates-box-title">Atenção aos Prazos:</p>
                                        <ul>
                                            <li><strong>Emissão e Envio (Holmes): </strong>{mock_vars.get('quinto_dia')} ({mock_vars.get('dia_semana')}), às 18:00.</li>
                                            <li><strong>Pagamento Programado: </strong> {mock_vars.get('primeiro_dia')} ({mock_vars.get('dia_semana_e')}).</li>
                                        </ul>
                                        <p style="margin: 12px 0 0 0; font-size: 14px; color: #666;">
                                            <em>Obs: Caso seja lançada posteriormente, o pagamento será feito em outra data, conforme prazo do Holmes.</em>
                                            <em> Reforçamos que as Notas Fiscais de Serviço Prestado de Pessoa Jurídica passam a ser lançadas na plataforma Holmes, não sendo mais necessário responder a este e-mail.</em>
                                        </p>
                                    </div>
                                    
                                    <h3 class="section-title">🧾&nbsp;&nbsp;Dados para Conferência</h3>
                                    {tabela_html}

                                    <h3 class="section-title">⚠️&nbsp;&nbsp;Instruções de Lançamento</h3>
                                    
                                    <div class="info-box">
                                        <strong>Pontos de Atenção:</strong><br><br>
                                        1. Observar o <strong>Centro de Custo Contábil</strong> indicado na tabela acima ao preencher no Holmes.
                                        <em>{cabechalhoa}</em>
                                    </div>
                                    
                                    <div style="background-color: #eef2ff; border: 1px solid #c7d2fe; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                                        <strong>Referência da NF no Holmes:</strong><br>
                                        Ao abrir o processo, selecione a descrição: <br>
                                        <span style="background-color: #fff; padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; font-weight: bold; display: inline-block; margin-top: 5px; color: #d93025;">{mock_vars.get('referencia_holmes')}</span>
                                    </div>
                                        <!-- SEÇÃO DE VÍDEO ADICIONADA (DO EMAIL ANTIGO) -->
                                        <div class="video-box">
                                            <p style="margin: 0 0 10px 0; font-weight: bold; color: #333;">Dúvidas de como fazer?</p>
                                            <p style="margin: 0; font-size: 14px;">Segue abaixo vídeo explicativo de como efetuar o lançamento no Holmes:</p>
                                            <a href="https://drive.google.com/file/d/1O44vaOfZPJpXds0AxgtMQVURK8coU__8/view?usp=sharing" target="_blank" class="btn-video">
                                                ▶ Assistir Vídeo
                                            </a>
                                        </div>
                                        <!-- FIM SEÇÃO DE VÍDEO -->
                                    
                                    <p style="margin-top: 30px;">
                                        Atenciosamente,<br>
                                        <strong>Departamento Pessoal</strong>
                                    </p>
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td class="footer-block">
                                <table style="font-family: Arial, sans-serif; font-size: 12px;" cellpadding="10" cellspacing="0" border="0">
                                 <tbody><tr>
                                   <td style="font-size: 18px; color: rgb(0, 0, 0);" class="AssNome">Silmara Silva</td>
                                   <td style="text-align: left;"><img src="https://www.grupo-new.com/logos/_img/0.png" border="0" style="max-width: 300px; height: auto; max-height: 100px;" id="imgFlag" width="200"></td>
                                 </tr>
                                 <tr style="background: #ebebeb; color:#000;">
                                   <td valign="top">
                                     <b class="AssSetor">Gerente DP</b><br>
                                     <span class="AssTelefone">(85) 4005-1427</span><br>
                                     <a href="mailto:silmara.silva@gruponewland.com.br" style="color:#000; text-decoration: none;" class="AssEmail">silmara.silva@gruponewland.com.br</a>
                                   </td>
                                   <td style="text-align: right; padding-left: 10px;" class="logoGrupo" valign="top"></td>
                                 </tr>
                                 <tr style="background: rgb(0, 0, 0); color: rgb(255, 255, 255);" class="rodape">
                                   <td colspan="2" class="AssEndereco">Av. Washington Soares, 1550 • Fortaleza / Ceará / Brasil</td>
                                 </tr>
                               </tbody></table>
                                
                               <p style="font-size:10px; color:#666; font-family: Arial">Esta mensagem pode conter informação
              confidencial ou privilegiada, sendo seu sigilo protegido por lei. Se você não for o
              destinatário ou a pessoa autorizada a receber esta mensagem, não pode usar, copiar ou divulgar as
              informações nela contidas ou tomar qualquer ação baseada nessas
              informações. Se você recebeu esta mensagem por engano, por favor, avise imediatamente ao
              remetente, respondendo o e-mail e em seguida apague-a. Agradecemos sua cooperação.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return corpo_email