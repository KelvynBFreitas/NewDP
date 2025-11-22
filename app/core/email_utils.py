import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import time

def preparar_email(html_content, destinatario, remetente):
    """
    Cria o objeto da mensagem MIME com o HTML gerado.
    """
    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = "Aprovação de Gratificação Anual - Pendências"
    
    # Anexa o corpo HTML
    msg.attach(MIMEText(html_content, 'html'))
    
    return destinatario, msg

def enviar_emails_em_lote(lista_mensagens):
    """
    Recebe uma lista de tuplas (destinatario, objeto_msg).
    Abre a conexão SMTP UMA vez e envia todos os e-mails da lista.
    """
    # Configurações do .env
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com") # Exemplo: Outlook/Exchange
    smtp_port = int(os.getenv("EMAIL_PORT", 587))
    smtp_user = os.getenv("EMAIL_USER")
    smtp_password = os.getenv("EMAIL_PASSWORD")

    if not lista_mensagens:
        print(">>> Lista de e-mails vazia. Nada a enviar.")
        return

    print(f"--- INICIANDO CONEXÃO SMTP COM {smtp_server} ---")
    
    context = ssl.create_default_context()
    
    try:
        # Conecta ao servidor
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            
            total = len(lista_mensagens)
            print(f"--- PREPARANDO PARA ENVIAR {total} E-MAILS ---")

            for index, (destinatario, msg) in enumerate(lista_mensagens):
                try:
                    # Envio real
                    server.sendmail(smtp_user, destinatario, msg.as_string())
                    
                    print(f"[{index+1}/{total}] Sucesso: {destinatario}")
                    
                    # Pequeno delay (1s) para evitar bloqueio de SPAM e 
                    # manter o loading do frontend visível para o usuário
                    time.sleep(0.2) 
                    
                except Exception as e:
                    print(f"[{index+1}/{total}] ERRO ao enviar para {destinatario}: {e}")

    except Exception as e:
        print(f"ERRO CRÍTICO DE CONEXÃO SMTP: {e}")
        # Opcional: relançar o erro se quiser que o backend retorne 500
        # raise e 

    print("--- CONEXÃO SMTP ENCERRADA ---")