import os
import sys
import time
import requests
import json
import re
import subprocess

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS ---
def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except:
        pass

# Garante yt-dlp
try:
    import yt_dlp
except ImportError:
    install_package("yt-dlp")
    import yt_dlp

# Garante cloudscraper
try:
    import cloudscraper
except ImportError:
    install_package("cloudscraper")
    import cloudscraper

from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES DO SISTEMA ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')
BUTTON_LINK = os.environ.get('BUTTON_LINK') 

# Inicializa o scraper
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

HEADERS_PT = {
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def check_ffmpeg():
    """Verifica e tenta instalar o FFmpeg se necessário."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("⚠️ FFmpeg não encontrado. Tentando instalar via apt-get...")
        try:
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', 'ffmpeg', '-y'], check=True)
            return True
        except Exception as e:
            print(f"❌ Falha ao instalar FFmpeg: {e}")
            return False

def get_direct_video_url(page_url):
    """Extrai link direto com yt-dlp."""
    print(f"🕵️‍♂️ Extraindo link real: {page_url}")
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'socket_timeout': 30,
        'user_agent': HEADERS_PT['User-Agent'],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
            return info.get('url')
    except Exception as e:
        print(f"⚠️ Erro yt-dlp: {e}")
        return None

def generate_snippet(video_direct_url, duration=3):
    """Gera recorte de 3 segundos."""
    output_file = f"video_{int(time.time())}.mp4"
    print(f"✂️ Gerando recorte de {duration}s...")
    
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-headers', f'User-Agent: {HEADERS_PT["User-Agent"]}\r\nReferer: https://www.xvideos.com/\r\n',
        '-ss', '00:00:10', # Começa aos 10s para evitar intros
        '-t', str(duration),
        '-i', video_direct_url,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32',
        '-c:a', 'aac', '-b:a', '64k',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_file
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            return output_file
    except Exception as e:
        print(f"⚠️ Erro FFmpeg: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    return None

def send_to_telegram(data):
    """Envia vídeo com botão de checkout."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    
    caption = f"🚨 <b>{data['titulo']}</b>\n\n"
    if CUSTOM_CAPTION:
        caption += f"💎 {CUSTOM_CAPTION}\n\n"
    else:
        caption += "🔞 <b>CONTEÚDO COMPLETO DISPONÍVEL!</b>\n"
        caption += "✓ Vídeo Unitário: R$ 3,99\n"
        caption += "✓ Acesso Vitalício (+5000 vídeos): R$ 19,99\n\n"
    
    caption += "👇 <b>LIBERA O ACESSO AGORA:</b>"

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔓 LIBERAR VÍDEO COMPLETO", "url": BUTTON_LINK}],
            [{"text": "⭐ PACK VITALÍCIO - R$ 19,99", "url": BUTTON_LINK}]
        ]
    }

    try:
        with open(data['path'], 'rb') as f:
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML',
                'reply_markup': json.dumps(reply_markup)
            }
            r = requests.post(api_url, data=payload, files={'video': f}, timeout=120)
            res = r.json()
            if res.get('ok'):
                print("✅ Enviado com sucesso!")
            else:
                print(f"❌ Erro Telegram: {res.get('description')}")
        os.remove(data['path'])
    except Exception as e:
        print(f"❌ Erro envio: {e}")

if __name__ == "__main__":
    # Verifica qual variável está faltando para debug claro
    missing = []
    if not TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if not TARGET_URL: missing.append("TARGET_URL")
    if not BUTTON_LINK: missing.append("BUTTON_LINK")

    if missing:
        print(f"❌ Faltam configurações no GitHub Actions: {', '.join(missing)}")
        sys.exit(1)

    if not check_ffmpeg():
        sys.exit(1)

    print("--- SNIPER ENGINE V3.5 ATIVADA ---")
    
    links = []
    try:
        r = scraper.get(TARGET_URL, headers=HEADERS_PT, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        for b in blocks:
            if len(links) >= 15: break
            try:
                path = b.find('p', class_='title').find('a')['href']
                links.append(f"https://www.xvideos.com{path}")
            except: continue
    except:
        links = [TARGET_URL]

    if not links:
        print("⚠️ Nenhum vídeo encontrado.")
        sys.exit(1)

    for link in links:
        try:
            r_vid = scraper.get(link, headers=HEADERS_PT, timeout=15)
            soup_vid = BeautifulSoup(r_vid.text, 'html.parser')
            title = soup_vid.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
            
            v_url = get_direct_video_url(link)
            if v_url:
                v_path = generate_snippet(v_url, duration=3)
                if v_path:
                    send_to_telegram({"path": v_path, "titulo": title})
                    time.sleep(12)
        except Exception as e:
            print(f"⚠️ Erro item: {e}")
