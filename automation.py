import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup

# Configurações do ambiente
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def get_direct_video_url(page_url):
    print(f"🕵️ Extraindo link real: {page_url}")
    # Comando simplificado para evitar timeouts no GitHub Actions
    cmd = ['yt-dlp', '-g', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', page_url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        url = result.stdout.strip()
        if url: return url
    except: return None
    return None

def generate_snippet(video_direct_url):
    output_file = f"video_{int(time.time())}.mp4"
    # Corte de 20 segundos para o grupo
    cmd = ['ffmpeg', '-y', '-ss', '00:00:05', '-t', '20', '-i', video_direct_url, 
           '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', '-c:a', 'aac', output_file]
    try:
        subprocess.run(cmd, check=True, timeout=60)
        return output_file if os.path.exists(output_file) else None
    except: return None

def send_to_telegram(path, titulo):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    caption = f"🔞 <b>{titulo}</b>\n\n👇 <b>ASSISTA COMPLETO ABAIXO</b> 👇"
    
    # ESTRUTURA DE BOTÕES DE ALTA CONVERSÃO
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
        'reply_markup': json.dumps(reply_markup)
    }
    
    with open(path, 'rb') as f:
        r = requests.post(api_url, data=payload, files={'video': f})
        return r.json().get('ok')

if __name__ == "__main__":
    print(f"🚀 Sniper Engine Iniciada - Alvo: {TARGET_URL}")
    
    # Verifica se é link de vídeo único ou categoria
    links = []
    if "/video." in TARGET_URL:
        links = [TARGET_URL]
    else:
        # Lógica de scraping para categorias
        res = scraper.get(TARGET_URL)
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.select('p.title a'):
            links.append(f"https://www.xvideos.com{a['href']}")
    
    print(f"🎯 Total de vídeos encontrados: {len(links)}")

    for url in links[:5]: # Limite de 5 para não estourar o tempo do GitHub
        video_direct = get_direct_video_url(url)
        if video_direct:
            path = generate_snippet(video_direct)
            if path:
                if send_to_telegram(path, "Conteúdo Exclusivo"):
                    print("✅ Enviado com sucesso!")
                os.remove(path)
