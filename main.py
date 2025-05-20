from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import openai
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

app = FastAPI()

# Libera o frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, use domínios reais
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo de dados esperado do frontend
class Formulario(BaseModel):
    nome: str
    email: str | None = None
    respostas: list[str]

# Rota principal
@app.post("/processar")
async def processar(form: Formulario):
    nome_exibido = form.nome or "Anônimo"

    # Email administrativo com respostas brutas
    corpo_admin = f"Nome: {nome_exibido}\n\nRespostas:\n"
    for i, r in enumerate(form.respostas, start=1):
        corpo_admin += f"{i}. {r}\n"

    try:
        msg = EmailMessage()
        msg.set_content(corpo_admin)
        msg['Subject'] = 'Nova resposta ao questionário'
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print("Erro ao enviar e-mail ao admin:", str(e))

    # Criação do prompt
    prompt = f"""Usuário respondeu o seguinte questionário sobre estilo de vida.
Gere dicas personalizadas para melhorar a saúde e bem-estar, e diga também o que está bom e deve ser mantido.
Finaliza com uma mensagem de agradecimento pela participação.

Nome: {nome_exibido}
Respostas:
"""
    for i, r in enumerate(form.respostas, start=1):
        prompt += f"{i}. {r}\n"

    # Solicitação para a OpenAI
    try:
        resposta_openai = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um orientador de saúde e bem-estar."},
                {"role": "user", "content": prompt}
            ]
        )
        resposta_texto = resposta_openai.choices[0].message.content
    except Exception as e:
        print("Erro ao consultar OpenAI:", str(e))
        return {"resposta": f"Erro ao gerar resposta personalizada: {str(e)}"}

    # Formatar em HTML (básico)
    resposta_html = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px;">
    """
    for linha in resposta_texto.strip().split("\n"):
        linha = linha.strip()
        if linha.endswith(":") or linha.lower().startswith("sugestões") or linha.lower().startswith("o que está bom"):
            resposta_html += f"<h3 style='margin-top: 30px; color: #2a7f4f;'>{linha}</h3>"
        elif linha.startswith("1.") or linha.startswith("2.") or linha.startswith("3.") or linha.startswith("4.") or linha.startswith("5."):
            resposta_html += f"<p style='margin-left: 15px;'>{linha}</p>"
        else:
            resposta_html += f"<p>{linha}</p>"
    resposta_html += """
        <p style="margin-top: 40px;">Com carinho,<br><strong>Seu Orientador de Saúde e Bem-Estar</strong></p>
        </div>
    </body>
    </html>
    """

    for linha in resposta_texto.strip().split("\n"):
        linha = linha.strip()
        if linha.startswith("**") and "**" in linha[2:]:
            # Formatação de título: **Título:**
            titulo = linha.replace("**", "").split(":")[0]
            conteudo = linha.replace(f"**{titulo}**:", "").strip()
            resposta_html += f"<h4 style='margin-bottom:0.2em;'>{titulo}</h4><p>{conteudo}</p>"
        else:
            resposta_html += f"<p>{linha}</p>"
    resposta_html += "</div>"

    # Enviar resposta para o entrevistado (HTML)
    if form.email:
        try:
            msg_user = EmailMessage()
            msg_user['Subject'] = 'Sua análise personalizada de saúde e bem-estar'
            msg_user['From'] = EMAIL_SENDER
            msg_user['To'] = form.email
            msg_user.set_content(resposta_texto)  # versão simples
            msg_user.add_alternative(resposta_html, subtype='html')  # versão HTML

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
                smtp.send_message(msg_user)
        except Exception as e:
            print("Erro ao enviar e-mail para entrevistado:", str(e))

    # Retornar resposta ao frontend
    return {"resposta": resposta_texto}
