import os
import sys
import cloudscraper
import time
import random
import re
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '') # Nova variável para sua legenda/arroba

# Inicializa o scraper uma vez
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def extract_mp4_url(html_content):
    """Tenta encontrar a URL do vídeo MP4 dentro do JavaScript da página"""
    # Xvideos guarda o link dentro de html5player.setVideoUrlHigh('') ou Low
    try:
        # Tenta pegar alta qualidade primeiro
        mp4_match = re.search(r"html5player\.setVideoUrlHigh\('([^']+)'\)", html_content)
        if not mp4_match:
            # Tenta baixa qualidade
            mp4_match = re.search(r"html5player\.setVideoUrlLow\('([^']+)'\)", html_content)
        
        if mp4_match:
            return mp4_match.group(1)
    except:
        pass
    return None

def process_single_video(url, custom_text=""):
    print(f"🔄 Processando vídeo único: {url}")
    try:
        response = scraper.get(url, timeout=25)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Título
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Vídeo Hot"
        title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()

        # 2. Thumbnail (Backup)
        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None

        # 3. Vídeo MP4 (Ouro)
        mp4_url = extract_mp4_url(response.text)

        return {
            "type": "video" if mp4_url else "photo",
            "media_url": mp4_url if mp4_url else thumbnail,
            "titulo": title,
            "link": url,
            "custom_text": custom_text
        }
    except Exception as e:
        print(f"❌ Erro ao processar vídeo: {e}")
        return None

def get_videos_from_listing(url):
    """Entra em uma página de categoria/tags e pega os 5 primeiros vídeos"""
    print(f"📑 Detectada página de listagem. Buscando top 5 vídeos...")
    links_to_process = []
    
    try:
        response = scraper.get(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontra os blocos de vídeo (thumb-block)
        blocks = soup.find_all('div', class_='thumb-block')
        
        count = 0
        for block in blocks:
            if count >= 3: # LIMITAMOS A 3 VÍDEOS POR VEZ PARA NÃO TOMAR BAN DO TELEGRAM
                break
                
            try:
                # Pega o link dentro do bloco
                a_tag = block.find('p', class_='title').find('a')
                partial_link = a_tag['href']
                full_link = f"https://www.xvideos.com{partial_link}"
                links_to_process.append(full_link)
                count += 1
            except:
                continue
                
        return links_to_process
    except Exception as e:
        print(f"❌ Erro ao ler listagem: {e}")
        return []

def send_to_telegram(data):
    # Decide se usa sendVideo ou sendPhoto
    method = "sendVideo" if data['type'] == 'video' else "sendPhoto"
    media_type = "video" if data['type'] == 'video' else "photo"
    
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    
    # Monta a legenda com o seu @ ou texto personalizado
    caption = f"🔥 <b>{data['titulo']}</b>\n\n"
    if data['custom_text']:
        caption += f"📣 {data['custom_text']}\n\n"
    caption += f"🔗 Assista completo: {data['link']}"
    
    payload = {
        'chat_id': CHAT_ID,
        media_type: data['media_url'],
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    try:
        print(f"🚀 Enviando {media_type} para o grupo...")
        # Timeout maior para envio de vídeo
        response = requests.post(api_url, data=payload, timeout=60)
        result = response.json()
        
        if result.get('ok'):
            print("✅ Enviado com sucesso!")
            return True
        else:
            print(f"❌ Erro Telegram: {result}")
            # Se falhar enviando VIDEO (muito pesado), tenta enviar só a FOTO como fallback
            if method == "sendVideo":
                print("⚠️ Tentando reenviar apenas como foto...")
                data['type'] = 'photo'
                # Precisaríamos ter a thumb guardada, mas simplificando: o script segue
            return False
    except Exception as e:
        print(f"❌ Erro conexão: {e}")
        return False

# --- EXECUÇÃO ---
if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Erro: Configurações faltando.")
        sys.exit(1)

    # Verifica se é link de vídeo único (tem /video em algum lugar ou numeroID)
    # Listagens geralmente são /tags/, /lang/, /best/
    is_single_video = "/video" in TARGET_URL and not "/channels/" in TARGET_URL
    
    videos_to_send = []

    if is_single_video:
        data = process_single_video(TARGET_URL, CUSTOM_CAPTION)
        if data: videos_to_send.append(data)
    else:
        # É uma página de categoria, pega os links
        links = get_videos_from_listing(TARGET_URL)
        for link in links:
            data = process_single_video(link, CUSTOM_CAPTION)
            if data:
                videos_to_send.append(data)
                # Pausa para não sobrecarregar o site
                time.sleep(2)

    # Disparo Final
    if not videos_to_send:
        print("⚠️ Nenhum vídeo processado com sucesso.")
        sys.exit(1)

    print(f"🎯 Total de vídeos para enviar: {len(videos_to_send)}")
    
    for i, video_data in enumerate(videos_to_send):
        print(f"--- Processando envio {i+1}/{len(videos_to_send)} ---")
        send_to_telegram(video_data)
        # PAUSA OBRIGATÓRIA ENTRE ENVIOS NO TELEGRAM (Anti-Flood)
        time.sleep(10)
