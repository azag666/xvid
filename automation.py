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

# SEU CHECKOUT FIXO E GARANTIDO
MEU_CHECKOUT = "https://telegramvipp.netlify.app/" 

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
    
    # COPY DE ALTA CONVERSÃO FOCADA NO TÍTULO E NA OFERTA
    caption = (
        f"🔞 <b>{titulo}</b>\n\n"
        f"🔥 <b>ACESSO VITALÍCIO LIBERADO!</b>\n\n"
        f"✅ <i>Sem cortes ou censura</i>\n"
        f"✅ <i>+100 vídeos novos por dia</i>\n"
        f"✅ <i>Acesso a TODOS os vídeos do canal</i>\n\n"
        f"👇 <b>CLIQUE NO BOTÃO VERDE ABAIXO POR APENAS R$ 9,99</b> 👇"
    )
    
    # Encurta o título do vídeo para garantir que cabe na largura do botão no telemóvel
    titulo_curto = titulo[:20] + "..." if len(titulo) > 20 else titulo
    
    # BOTÃO ÚNICO CHAMATIVO "VERDE" COM O TÍTULO E CTA
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
                # AUMENTADO DE 5 PARA 20 VÍDEOS POR DISPARO
                if len(links) >= 20: break 
                links.append(f"https://www.xvideos.com{a['href']}")
        except Exception as e:
            print(f"❌ Erro no Scraping: {e}")

    print(f"🎯 Total de vídeos para processar neste disparo: {len(links)}")

    for url in links:
        video_direct = get_direct_video_url(url)
        if video_direct:
            path = generate_snippet(video_direct)
            if path:
                # O título real do vídeo é extraído na função e repassado aqui
                try:
                    res_title = scraper.get(url, timeout=10)
                    soup_title = BeautifulSoup(res_title.text, 'html.parser')
                    title_real = soup_title.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
                except:
                    title_real = "VÍDEO EXCLUSIVO"

                if send_to_telegram(path, title_real):
                    print(f"✅ Enviado com sucesso: {title_real}")
                    time.sleep(5) # Pausa de 5s para o Telegram não considerar spam
                
                if os.path.exists(path): os.remove(path)
