import os
import sys
import requests
from bs4 import BeautifulSoup
import json

# --- CONFIGURAÇÕES ---
# Recupera as chaves secretas configuradas no GitHub
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')

def scrape_xvideos(url):
    print(f"🔄 Tentando acessar: {url}")
    
    # Headers para simular um navegador real (Chrome) e evitar erro 403
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        
        # Se o site bloquear (Erro 403) ou não encontrar (404)
        if response.status_code != 200:
            print(f"❌ Erro HTTP do site: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Título (Prioridade: Open Graph)
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else soup.title.string
        
        # Limpeza do título (remove o nome do site)
        if title:
            title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()
        else:
            title = "Vídeo sem título"
        
        # 2. Thumbnail (Prioridade: Open Graph)
        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None
        
        # Fallback (Plano B se não achar imagem no OG)
        if not thumbnail:
            link_img = soup.find("link", rel="image_src")
            thumbnail = link_img["href"] if link_img else None

        return {"titulo": title, "thumbnail": thumbnail}

    except Exception as e:
        print(f"❌ Erro técnico durante o scraping: {e}")
        return None

def send_to_telegram(data):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    caption = f"🔥 <b>{data['titulo']}</b>\n\nAssista completo aqui: {TARGET_URL}"
    
    payload = {
        'chat_id': CHAT_ID,
        'photo': data['thumbnail'],
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    try:
        print(f"🚀 Enviando para o Grupo (ID: {CHAT_ID})...")
        response = requests.post(api_url, data=payload, timeout=15)
        result = response.json()
        
        if result.get('ok'):
            print("✅ SUCESSO! Mensagem enviada.")
            return True
        else:
            # Mostra o erro exato que o Telegram devolveu
            print(f"❌ O Telegram recusou o envio. Motivo:")
            print(json.dumps(result, indent=2))
            return False
            
    except Exception as e:
        print(f"❌ Falha de conexão com o Telegram: {e}")
        return False

# --- EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    # 1. Validação de Segurança
    if not TELEGRAM_TOKEN:
        print("❌ ERRO FATAL: Secret 'TELEGRAM_TOKEN' não encontrada no GitHub.")
        sys.exit(1)
    if not CHAT_ID:
        print("❌ ERRO FATAL: Secret 'TELEGRAM_CHAT_ID' não encontrada no GitHub.")
        sys.exit(1)
    if not TARGET_URL:
        print("❌ ERRO FATAL: Nenhuma URL recebida para processar.")
        sys.exit(1)

    print("--- INICIANDO AUTOMAÇÃO ---")
    
    # 2. Extração de Dados
    dados = scrape_xvideos(TARGET_URL)
    
    if dados and dados['thumbnail']:
        print(f"📸 Dados extraídos com sucesso: {dados['titulo']}")
        
        # 3. Envio para o Telegram
        sucesso = send_to_telegram(dados)
        
        if not sucesso:
            print("⚠️ O script rodou, mas falhou ao enviar para o Telegram (Erro de API).")
            sys.exit(1) # Força erro no GitHub Actions para ficar VERMELHO
    else:
        print("⚠️ Falha ao extrair dados do site (Bloqueio ou Layout mudou).")
        sys.exit(1) # Força erro no GitHub Actions para ficar VERMELHO
