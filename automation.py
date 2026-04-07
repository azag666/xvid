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

# === COLOQUE O SEU LINK DE CHECKOUT AQUI ===
# Isso garante que o botão nunca falhe por culpa do painel frontal
MEU_CHECKOUT = "https://pay.kiwify.com.br/SEU_CHECKOUT_AQUI" 

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
    
    # COPY DA OFERTA IRRECUSÁVEL DE R$ 9,99
    caption = (
        f"🔞 <b>{titulo}</b>\n\n"
        f"🔥 <b>ACESSO VITALÍCIO LIBERADO!</b>\n\n"
        f"✅ <i>Sem cortes ou censura</i>\n"
        f"✅ <i>+100 vídeos novos por dia</i>\n"
        f"✅ <i>Acesso a TODOS os vídeos do canal</i>\n\n"
        f"👇 <b>CLIQUE NO BOTÃO VERDE ABAIXO POR APENAS R$ 9,99</b> 👇"
    )
    
    # Encurta o título do vídeo para garantir que cabe na largura do telemóvel
    titulo_curto = titulo[:18] + "..." if len(titulo) > 18 else titulo
    
    # BOTÃO ÚNICO CHAMATIVO COM EMOJIS VERDES E REDIRECIONAMENTO FIXO
    reply_markup = {
        "inline_keyboard": [
            [{"text": f"🟩 ASSISTIR: {titulo_curto} (R$ 9,99) ✅", "url": MEU_CHECKOUT}]
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
            print(f"Resposta Telegram: {r.text}") # Este log salva-o se o Telegram bloquear algo!
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
                if send_to_telegram(path, "VÍDEO EXCLUSIVO"):
                    print(f"✅ Enviado com sucesso!")
                if os.path.exists(path): os.remove(path)
