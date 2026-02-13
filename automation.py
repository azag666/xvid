import os
import requests
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
# Estas variáveis virão dos "Secrets" do GitHub
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')  # ID do Grupo (ex: -100xxxxxxxx)
TARGET_URL = os.environ.get('TARGET_URL')

def scrape_xvideos(url):
    """
    Acessa a URL e extrai as meta-tags (Título e Imagem)
    usando cabeçalhos de navegador para evitar bloqueios 403.
    """
    # Headers obrigatórios para o site não bloquear o bot
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    print(f"🔄 Acessando: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            print(f"❌ Erro HTTP ao acessar site: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Tenta pegar o Título "limpo" (Open Graph)
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else soup.title.string
        
        # Limpeza estética do título
        if title:
            title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()
        else:
            title = "Vídeo sem título"
        
        # 2. Tenta pegar a Thumbnail (Open Graph)
        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None
        
        # Fallback se não achar imagem no OG
        if not thumbnail:
             link_img = soup.find("link", rel="image_src")
             thumbnail = link_img["href"] if link_img else None

        return {"titulo": title, "thumbnail": thumbnail}

    except Exception as e:
        print(f"❌ Erro crítico de scraping: {e}")
        return None

def send_to_telegram(data):
    """Envia a foto com legenda para o grupo definido."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    caption = f"🔥 <b>{data['titulo']}</b>\n\nAssista completo aqui: {TARGET_URL}"
    
    payload = {
        'chat_id': CHAT_ID,
        'photo': data['thumbnail'],
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    try:
        print(f"🚀 Enviando para o grupo {CHAT_ID}...")
        response = requests.post(api_url, data=payload, timeout=15)
        result = response.json()
        
        if result.get('ok'):
            print("✅ Sucesso! Mensagem enviada para o grupo.")
            return True
        else:
            print(f"❌ Erro na API do Telegram: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Falha na conexão com Telegram: {e}")
        return False

# --- EXECUÇÃO ---
if __name__ == "__main__":
    # Verifica se as chaves existem
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Erro: Variáveis de ambiente faltando (TOKEN, CHAT_ID ou URL).")
        exit(1)

    print("--- INICIANDO AUTOMAÇÃO ---")
    
    # 1. Extrair dados
    dados = scrape_xvideos(TARGET_URL)
    
    if dados and dados['thumbnail']:
        print(f"📸 Conteúdo encontrado: {dados['titulo']}")
        # 2. Enviar para o grupo
        send_to_telegram(dados)
    else:
        print("⚠️ Não foi possível extrair título ou imagem. Verifique o link.")
        exit(1)
