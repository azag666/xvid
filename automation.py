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

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def get_direct_video_url(page_url):
    print(f"🕵️ Extraindo link real: {page_url}")
    # Comando para obter a URL direta do vídeo via yt-dlp
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
    # Comando FFmpeg para recortar os primeiros 20 segundos
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
    caption = f"🔞 <b>{titulo}</b>\n\n👇 <b>TOQUE NO BOTÃO ABAIXO PARA LIBERAR</b> 👇"
    
    # ESTRUTURA DE CALLBACK (Conecta com o seu vendedor.py para gerar PIX no chat)
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔥 DESBLOQUEAR VÍDEO (R$ 16,99)", "callback_data": "pix_1699"}],
            [{"text": "💎 ACESSO VIP (R$ 29,99)", "callback_data": "pix_2999"}]
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
        print("❌ ERRO: Faltam Secrets no GitHub (TOKEN, CHAT_ID ou TARGET_URL)")
        sys.exit(1)

    print(f"🚀 Sniper Engine Iniciada - Alvo: {TARGET_URL}")
    
    links = []
    # Verifica se o link fornecido é um vídeo direto ou uma página de listagem
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
            print(f"❌ Erro no Scraping da página: {e}")

    print(f"🎯 Total de vídeos para processar: {len(links)}")

    for url in links:
        video_direct = get_direct_video_url(url)
        if video_direct:
            path = generate_snippet(video_direct)
            if path:
                success = send_to_telegram(path, "CONTEÚDO EXCLUSIVO LIBERADO")
                if success:
                    print(f"✅ Vídeo enviado com sucesso: {url}")
                    time.sleep(5) # Intervalo para evitar spam
                if os.path.exists(path): os.remove(path)
