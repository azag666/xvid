import os
import sys
import cloudscraper
import time
import requests
import json
import re
from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def extract_mp4_url(html_content):
    """Tenta encontrar a URL do vídeo MP4"""
    try:
        mp4_match = re.search(r"html5player\.setVideoUrlHigh\('([^']+)'\)", html_content)
        if not mp4_match:
            mp4_match = re.search(r"html5player\.setVideoUrlLow\('([^']+)'\)", html_content)
        if mp4_match:
            return mp4_match.group(1)
    except:
        pass
    return None

def process_single_video(url, custom_text=""):
    print(f"🔄 Processando: {url}")
    try:
        response = scraper.get(url, timeout=25)
        if response.status_code != 200: 
            print(f"❌ Erro HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Título
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Vídeo Hot"
        title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()

        # Thumbnail
        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None
        
        # Vídeo MP4
        mp4_url = extract_mp4_url(response.text)

        # RETORNA AMBOS (Vídeo e Foto) para ter Plano B
        return {
            "type": "video" if mp4_url else "photo",
            "video_url": mp4_url,
            "photo_url": thumbnail,
            "titulo": title,
            "link": url,
            "custom_text": custom_text
        }
    except Exception as e:
        print(f"❌ Erro scraper: {e}")
        return None

def get_videos_from_listing(url):
    """Busca vídeos em páginas de categoria"""
    print(f"📑 Lendo lista de vídeos...")
    links = []
    try:
        response = scraper.get(url, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        
        count = 0
        for block in blocks:
            if count >= 3: break # Limite de 3 para evitar spam
            try:
                a_tag = block.find('p', class_='title').find('a')
                full_link = f"https://www.xvideos.com{a_tag['href']}"
                links.append(full_link)
                count += 1
            except: continue
        return links
    except Exception as e:
        print(f"❌ Erro lista: {e}")
        return []

def send_payload(method, payload):
    """Função auxiliar para envio"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, data=payload, timeout=60)
        return r.json()
    except Exception as e:
        return {'ok': False, 'description': str(e)}

def smart_send(data):
    """Tenta enviar vídeo, se falhar, envia foto"""
    
    caption = f"🔥 <b>{data['titulo']}</b>\n\n"
    if data['custom_text']:
        caption += f"📣 {data['custom_text']}\n\n"
    caption += f"🔗 Assista completo: {data['link']}"

    # TENTATIVA 1: Enviar Vídeo (Se existir)
    if data['type'] == 'video' and data['video_url']:
        print("🎥 Tentando enviar vídeo MP4...")
        res = send_payload('sendVideo', {
            'chat_id': CHAT_ID,
            'video': data['video_url'],
            'caption': caption,
            'parse_mode': 'HTML'
        })
        
        if res.get('ok'):
            print("✅ Vídeo enviado com sucesso!")
            return True
        else:
            print(f"⚠️ Falha ao enviar vídeo: {res.get('description')}")
            print("🔄 Ativando PLANO B: Enviar Foto...")

    # TENTATIVA 2: Enviar Foto (Fallback ou Padrão)
    if data['photo_url']:
        print("📸 Enviando Thumbnail...")
        res = send_payload('sendPhoto', {
            'chat_id': CHAT_ID,
            'photo': data['photo_url'],
            'caption': caption,
            'parse_mode': 'HTML'
        })
        
        if res.get('ok'):
            print("✅ Foto enviada com sucesso!")
            return True
        else:
            print(f"❌ Falha ao enviar foto: {res.get('description')}")
            return False
            
    return False

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Configurações faltando.")
        sys.exit(1)

    # Lógica de seleção (Lista ou Único)
    urls_to_process = []
    # Detecta se é video unico pela URL
    if "/video" in TARGET_URL and "/channels/" not in TARGET_URL:
        urls_to_process.append(TARGET_URL)
    else:
        urls_to_process = get_videos_from_listing(TARGET_URL)

    if not urls_to_process:
        print("❌ Nenhum link encontrado.")
        sys.exit(1)

    print(f"🎯 Processando {len(urls_to_process)} itens...")
    
    success_count = 0
    for url in urls_to_process:
        data = process_single_video(url, CUSTOM_CAPTION)
        if data:
            if smart_send(data):
                success_count += 1
            # Pausa para não tomar flood
            time.sleep(5)
    
    # Se nenhum envio deu certo, marca o GitHub como falha
    if success_count == 0:
        print("❌ Todos os envios falharam.")
        sys.exit(1)
        
    print(f"🏁 Finalizado. {success_count}/{len(urls_to_process)} enviados.")
