import os
import sys
import time
import requests
import json
import re
import subprocess

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS CRÍTICAS ---
# Garante que temos o yt-dlp (melhor extrator de vídeos do mundo)
try:
    import yt_dlp
except ImportError:
    print("⬇️ Instalando yt-dlp automaticamente...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
    import yt_dlp

try:
    import cloudscraper
except ImportError:
    print("⬇️ Instalando cloudscraper automaticamente...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper"])
    import cloudscraper

from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')

# Configura o scraper simulando um navegador
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

# Cabeçalhos para FORÇAR o conteúdo em Português (apenas para o Título)
HEADERS_PT = {
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://www.google.com/'
}

def get_direct_video_url(page_url):
    """
    Usa yt-dlp para extrair a URL direta do vídeo (MP4 ou HLS).
    Muito mais robusto que Regex.
    """
    print("🕵️‍♂️ Extraindo link real do vídeo com yt-dlp...")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best', # Tenta pegar a melhor qualidade MP4
        'socket_timeout': 10,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info com download=False apenas pega os metadados
            info = ydl.extract_info(page_url, download=False)
            return info.get('url') # Retorna o link direto do arquivo de vídeo
    except Exception as e:
        print(f"⚠️ Falha no yt-dlp: {e}")
        return None

def generate_snippet(video_direct_url, duration=45):
    """
    Usa o FFmpeg para baixar e cortar os primeiros X segundos do vídeo.
    """
    output_file = f"snippet_{int(time.time())}.mp4"
    print(f"✂️ Gerando recorte de {duration} segundos...")
    
    # Adicionamos -headers para garantir que o ffmpeg consiga ler se o link pedir
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-headers', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 
        '-i', video_direct_url,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
        '-c:a', 'aac', '-b:a', '64k',
        output_file
    ]
    
    try:
        # Timeout aumentado para 3 minutos, pois baixar vídeo demora
        subprocess.run(cmd, check=True, timeout=180)
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            print(f"✅ Recorte gerado com sucesso: {output_file}")
            return output_file
    except Exception as e:
        print(f"⚠️ Falha no FFmpeg: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    
    return None

def process_single_video(url, custom_text=""):
    print(f"🔄 Processando página: {url}")
    try:
        # 1. Pega Título e Thumb usando CloudScraper (para garantir PT-BR)
        response = scraper.get(url, headers=HEADERS_PT, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Vídeo Hot"
        title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()

        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None
        
        # 2. Pega URL do Vídeo usando yt-dlp (Blindado)
        video_direct_url = get_direct_video_url(url)
        
        # 3. Gera o recorte se conseguiu o link
        local_video_path = None
        if video_direct_url:
            local_video_path = generate_snippet(video_direct_url)
        else:
            print("❌ Não foi possível extrair o link do vídeo.")

        return {
            "type": "video" if local_video_path else "photo",
            "video_path": local_video_path,
            "photo_url": thumbnail,
            "titulo": title,
            "link": url,
            "custom_text": custom_text
        }
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return None

def get_videos_from_listing(url):
    """Busca vídeos em páginas de categoria"""
    print(f"📑 Lendo lista de vídeos (PT-BR)...")
    links = []
    try:
        response = scraper.get(url, headers=HEADERS_PT, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        
        count = 0
        for block in blocks:
            if count >= 5: break 
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

def send_payload(method, payload, files=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if files:
            r = requests.post(url, data=payload, files=files, timeout=120)
        else:
            r = requests.post(url, data=payload, timeout=60)
        return r.json()
    except Exception as e:
        return {'ok': False, 'description': str(e)}

def smart_send(data):
    # Legenda Clean
    caption = f"🇧🇷 <a href=\"{data['link']}\"><b>{data['titulo']}</b></a>"
    if data['custom_text']:
        caption += f"\n\n📣 {data['custom_text']}"

    # Prioridade: Vídeo
    if data['type'] == 'video' and data['video_path']:
        print("🎥 Enviando vídeo para o Telegram...")
        try:
            with open(data['video_path'], 'rb') as video_file:
                res = send_payload('sendVideo', {
                    'chat_id': CHAT_ID,
                    'caption': caption,
                    'parse_mode': 'HTML',
                    'supports_streaming': 'true'
                }, files={'video': video_file})
            
            os.remove(data['video_path'])
            
            if res.get('ok'):
                print("✅ Vídeo enviado!")
                return True
            else:
                print(f"⚠️ Erro Telegram (Vídeo): {res.get('description')}")
        except Exception as e:
            print(f"⚠️ Erro arquivo: {e}")

    # Fallback: Foto
    if data['photo_url']:
        print("🔄 Enviando Foto (Fallback)...")
        res = send_payload('sendPhoto', {
            'chat_id': CHAT_ID,
            'photo': data['photo_url'],
            'caption': caption,
            'parse_mode': 'HTML'
        })
        
        if res.get('ok'):
            print("✅ Foto enviada!")
            return True
            
    return False

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Configurações faltando.")
        sys.exit(1)

    urls_to_process = []
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
            time.sleep(5)
    
    if success_count == 0:
        print("❌ Todos os envios falharam.")
        sys.exit(1)
        
    print(f"🏁 Finalizado. {success_count}/{len(urls_to_process)} enviados.")
