import os
import requests
from dotenv import load_dotenv
from google import genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. Carrega as chaves
load_dotenv("API.env")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")

def filtrar_novos_eventos(eventos_brutos):
    # Tenta ler o histórico; se não existir, cria uma memória vazia
    try:
        with open("historico.txt", "r") as f:
            historico = set(f.read().splitlines())
    except FileNotFoundError:
        historico = set()

    eventos_ineditos = []
    novos_links = []
    
    for e in eventos_brutos:
        # Só aprova o evento se o link dele nunca tiver sido enviado
        if e['link'] not in historico:
            eventos_ineditos.append(e)
            novos_links.append(e['link'])
            
    return eventos_ineditos, novos_links

def atualizar_historico(novos_links):
    # Adiciona os links inéditos de hoje no final do arquivo de memória
    with open("historico.txt", "a") as f:
        for link in novos_links:
            f.write(f"{link}\n")

# 2. Inicializa o NOVO cliente do Gemini
cliente_gemini = genai.Client(api_key=GEMINI_KEY)

# 3. Função de Busca (Mantendo os parâmetros idênticos)
def buscar_eventos_tecnologia():
    print("Iniciando varredura de eventos...")
    url = "https://serpapi.com/search"
    
    params = {
      "q": "(evento OR congresso OR meetup OR 'deep dive' OR summit) AND (tecnologia OR 'inteligência artificial' OR 'AI' OR OCI OR AWS OR 'Microsoft'OR 'IA')",
      "location": "Brazil",
      "hl": "pt",
      "gl": "br",
      "num": 50, 
      "api_key": SERPAPI_KEY
    }

    resposta = requests.get(url, params=params)
    results = resposta.json()
    
    if "error" in results:
        print(f"ERRO NA API DE BUSCA: {results['error']}")
        return []
    
    eventos_brutos = []
    
    if "organic_results" in results:
        for item in results["organic_results"]:
            evento = {
                "titulo": item.get("title"),
                "link": item.get("link"),
                "descricao": item.get("snippet")
            }
            eventos_brutos.append(evento)
            
    print(f"Foram encontrados {len(eventos_brutos)} resultados brutos no Google.")
    return eventos_brutos

# 4. Função do Gemini
def filtrar_com_gemini(eventos_brutos):
    print("Processando dados com o Gemini...")
    
    texto_bruto = "\n".join([f"- Título: {e['titulo']}\n  Descrição: {e['descricao']}\n  Link: {e['link']}\n" for e in eventos_brutos])
    
    prompt = f"""
    Atue como um Analista Sênior de Tecnologia auxiliando um Engenheiro de Dados e Especialista em Cloud.
    Eu fiz uma varredura na web buscando eventos relevantes de tecnologia. 
    Analise a lista bruta abaixo e faça o seguinte:
    1. Remova eventos que não sejam do Brasil.
    2. Remova anúncios patrocinados genéricos, vagas de emprego ou cursos básicos.
    3. Mantenha APENAS eventos técnicos de alto nível, workshops, summits ou meetups focados em: Cloud (OCI, AWS, Azure), Engenharia de Dados, Data Lakes, Inteligência Artificial, Agentes Autônomos e Governança/Regulação.
    4. Formate a resposta final em HTML limpo, usando uma lista (<ul> e <li>), destacando em negrito (<b>) o nome do evento, seguido de uma breve descrição do porquê é relevante para a área, e o link clicável.
    5. REGRA ESTRITA DE SAÍDA: Retorne ABSOLUTAMENTE APENAS as tags HTML da lista (<ul> e <li>). NÃO escreva saudações, NÃO explique suas decisões, NÃO escreva introduções ou conclusões.
    
    Aqui está a lista bruta:
    {texto_bruto}
    """
    
    resposta = cliente_gemini.models.generate_content(
        model='gemini-3.5-flash', 
        contents=prompt
    )
    
    return resposta.text
    
# 5. Função de Envio de E-mail (Corrigida a estrutura do try/except)
def enviar_email(html_eventos):
    print("Enviando e-mail...")
    
    meu_email = os.getenv("GMAIL_USER")
    minha_senha = os.getenv("GMAIL_PASSWORD") 
    
    if not meu_email or not minha_senha:
        print("ERRO: Credenciais do Gmail não encontradas no arquivo API.env.")
        return

    msg = MIMEMultipart()
    msg['From'] = meu_email
    msg['To'] = meu_email
    msg['Subject'] = "Seu Radar Diário de Eventos de TI (Data & Cloud)"
    
    corpo_email = f"""
    <html>
      <body>
        <h2>Radar de Eventos Atualizado</h2>
        <p>Aqui estão as oportunidades e eventos técnicos garimpados para você hoje:</p>
        {html_eventos}
      </body>
    </html>
    """
    
    msg.attach(MIMEText(corpo_email, 'html'))
    
    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(meu_email, minha_senha)
        texto = msg.as_string()
        servidor.sendmail(meu_email, meu_email, texto)
        servidor.quit()
        print("E-mail enviado com sucesso! Verifique a sua caixa de entrada (e a pasta de SPAM).")
    except Exception as e:
        print(f"Erro ao enviar o e-mail: {e}")

# 6. O Bloco Principal
if __name__ == "__main__":
    if not SERPAPI_KEY or not GEMINI_KEY:
        print("ERRO CRÍTICO: Chaves não carregadas.")
    else:
        resultados_brutos = buscar_eventos_tecnologia()
        
        if resultados_brutos:
            eventos_ineditos, novos_links = filtrar_novos_eventos(resultados_brutos)
            
            if eventos_ineditos:
                print(f"Oba! Temos {len(eventos_ineditos)} eventos inéditos hoje.")
                
                html_eventos = filtrar_com_gemini(eventos_ineditos)
                
                html_eventos = html_eventos.replace("```html", "").replace("```", "").strip()
                
                enviar_email(html_eventos)
                
                atualizar_historico(novos_links)
            else:
                print("Todos os eventos encontrados hoje já foram enviados anteriormente. Nada de spam!")
        else:
            print("A varredura foi concluída, mas nenhum evento orgânico foi encontrado.")
