import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup

# Configurações extraídas das Secrets do GitHub
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
# Link de destino configurado no seu painel ou Secret
BUTTON_LINK = os.environ.get('BUTTON_LINK')

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def get_direct_video_url(page_url):
    print(f"🕵️ Extraindo link real: {page_url}")
    cmd = ['yt-dlp', '-g', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', page_url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        url = result.stdout.strip()
        if url: return url
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}")
    return None

def generate_snippet(video_direct_url):
    output_file = f"video_{int(time.time())}.mp4"
    print("✂️ Criando teaser de 20 segundos...")
    cmd = [
        'ffmpeg', '-y', '-ss', '00:00:05', '-t', '20', 
        '-i', video_direct_url, 
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', 
        '-c:a', 'aac', '-b:a', '64k', output_file
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        return output_file if os.path.exists(output_file) else None
    except Exception as e:
        print(f"❌ Erro FFmpeg: {e}")
    return None

def send_to_telegram(path, titulo):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    caption = f"🔞 <b>{titulo}</b>\n\n👇 <b>ASSISTA AO VÍDEO COMPLETO ABAIXO</b> 👇"
    
    # Define o link de checkout. Se não houver, usa um fallback.
    link_final = BUTTON_LINK if BUTTON_LINK and BUTTON_LINK != "none" else "https://t.me/seu_contato"
    
    # ESTRUTURA DE BOTÃO URL (Redireciona para o checkout externo)
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔥 DESBLOQUEAR CONTEÚDO COMPLETO", "url": link_final}],
            [{"text": "💎 ACESSO VIP VITALÍCIO", "url": link_final}]
        ]
    }
    
    payload = {
        'chat_id': CHAT_ID,
        'caption': caption,
        'parse_mode': 'HTML',
        'supports_streaming': 'true',
        'reply_markup': json.dumps(reply_markup)
    }
    
    try:
        with open(path, 'rb') as f:
            r = requests.post(api_url, data=payload, files={'video': f}, timeout=60)
            print(f"Resposta Telegram: {r.text}")
            return r.json().get('ok')
    except Exception as e:
        print(f"❌ Erro no envio: {e}")
        return False

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID or not TARGET_URL:
        print("❌ ERRO: Faltam configurações (TOKEN, CHAT_ID ou TARGET_URL)")
        sys.exit(1)

    print(f"🚀 Sniper Engine Iniciada - Alvo: {TARGET_URL}")
    
    links = []
    if "/video." in TARGET_URL:
        links = [TARGET_URL]
    else:
        try:
            res = scraper.get(TARGET_URL, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.select('p.title a'):
                if len(links) >= 5: break
                links.append(f"https://www.xvideos.com{a['href']}")
        except Exception as e:
            print(f"❌ Erro no Scraping: {e}")

    for url in links:
        video_direct = get_direct_video_url(url)
        if video_direct:
            path = generate_snippet(video_direct)
            if path:
                if send_to_telegram(path, "CONTEÚDO EXCLUSIVO LIBERADO"):
                    print(f"✅ Enviado com sucesso!")
                if os.path.exists(path): os.remove(path)
