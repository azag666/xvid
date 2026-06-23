import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

# 1. CAPTURA DE VARIÁVEIS DO FRONT-END
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL', '').strip()
CUSTOM_MEDIA_URL = os.environ.get('CUSTOM_MEDIA_URL', '').strip()

SCRAPE_LIMIT = int(os.environ.get('SCRAPE_LIMIT', '5') or '5')
VIDEO_DURATION = os.environ.get('VIDEO_DURATION', 'teaser')
WATERMARK_TEXT = os.environ.get('WATERMARK_TEXT', '').strip()
WATERMARK_POS = os.environ.get('WATERMARK_POS', 'bottom_right')

# Toggles de Interface
USE_SPOILER = os.environ.get('USE_SPOILER', 'true').lower() == 'true'
USE_TITLE = os.environ.get('USE_TITLE', 'true').lower() == 'true'
SEND_MODE = os.environ.get('SEND_MODE', 'single') # 'single' ou 'gallery'

CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')
RAW_BUTTONS = os.environ.get('DYNAMIC_BUTTONS', '[]')

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def traduzir_para_pt(texto):
    if not USE_TITLE: return ""
    try:
        texto_seguro = urllib.parse.quote(texto)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=pt&dt=t&q={texto_seguro}"
        res = requests.get(url, timeout=5)
        return res.json()[0][0][0]
    except: return texto

def get_direct_video_url(page_url):
    print(f"🕵️ Extraindo link: {page_url}", flush=True)
    cmd = ['yt-dlp', '-g', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', page_url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        url = result.stdout.strip()
        if url: return url
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}", flush=True)
    return None

def process_video(video_direct_url, index):
    output_file = f"video_{index}_{int(time.time())}.mp4"
    print(f"🎬 Processando vídeo {index}...", flush=True)
    
    cmd = ['ffmpeg', '-y']
    if VIDEO_DURATION == 'teaser': cmd.extend(['-ss', '00:00:05', '-t', '15'])
    cmd.extend(['-i', video_direct_url])
    
    if WATERMARK_TEXT:
        escaped_text = WATERMARK_TEXT.replace("'", "\\'")
        
        # Posições da marca d'água
        if WATERMARK_POS == 'top_left': pos = 'x=15:y=15'
        elif WATERMARK_POS == 'top_right': pos = 'x=w-tw-15:y=15'
        elif WATERMARK_POS == 'bottom_left': pos = 'x=15:y=h-th-15'
        elif WATERMARK_POS == 'center': pos = 'x=(w-tw)/2:y=(h-th)/2'
        else: pos = 'x=w-tw-15:y=h-th-15' # default bottom_right
        
        vf_filter = f"drawtext=text='{escaped_text}':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.6:{pos}"
        cmd.extend(['-vf', vf_filter])
        
    cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', '-c:a', 'aac', '-b:a', '64k', output_file])
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        return output_file if os.path.exists(output_file) else None
    except Exception as e:
        print(f"❌ Erro FFmpeg: {e}", flush=True)
    return None

def build_reply_markup():
    inline_keyboard = []
    try:
        botoes_lista = json.loads(RAW_BUTTONS)
        for b in botoes_lista: inline_keyboard.append([{"text": b['name'], "url": b['url']}])
    except: pass
    return json.dumps({"inline_keyboard": inline_keyboard}) if inline_keyboard else None

def build_caption(titulo_pt):
    cap = ""
    if USE_TITLE and titulo_pt: cap += f"🔞 <b>{titulo_pt}</b>\n\n"
    if CUSTOM_CAPTION: cap += f"{CUSTOM_CAPTION}\n\n"
    cap += f"👇 <b>ESCOLHA SUA OPÇÃO:</b> 👇"
    return cap

def send_gallery_mode(paths, titulo_pt):
    # Envia Galeria (Sem botões, limitação da API do Telegram)
    media_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    media_group = []
    files = {}
    
    for i, path in enumerate(paths):
        legenda = build_caption(titulo_pt) if i == 0 else ""
        media_group.append({
            'type': 'video', 'media': f'attach://video{i}', 
            'has_spoiler': USE_SPOILER, 'caption': legenda, 'parse_mode': 'HTML'
        })
        files[f'video{i}'] = open(path, 'rb')
        
    try:
        requests.post(media_url, data={'chat_id': CHAT_ID, 'media': json.dumps(media_group)}, files=files, timeout=120)
    finally:
        for f in files.values(): f.close()

    # Envia os Botões Separadamente na sequência
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload_msg = { 'chat_id': CHAT_ID, 'text': build_caption(titulo_pt), 'parse_mode': 'HTML', 'reply_markup': build_reply_markup() }
    requests.post(msg_url, data=payload_msg, timeout=30)
    return True

def send_single_mode(paths, titulos):
    # Envia Mídia, Copy e Botões TODOS JUNTOS em um único balão
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    reply_markup = build_reply_markup()
    
    for i, path in enumerate(paths):
        titulo_atual = titulos[i] if len(titulos) > i else "Conteúdo Premium"
        caption = build_caption(titulo_atual)
        
        payload = {
            'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML',
            'has_spoiler': str(USE_SPOILER).lower(), 'supports_streaming': 'true'
        }
        if reply_markup: payload['reply_markup'] = reply_markup
        
        try:
            with open(path, 'rb') as f:
                requests.post(api_url, data=payload, files={'video': f}, timeout=60)
            time.sleep(3)
        except Exception as e:
            print(f"❌ Erro no envio individual: {e}")
    return True

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID: sys.exit(1)

    paths_to_send = []
    titulos = []

    # Extração
    if CUSTOM_MEDIA_URL:
        video_direct = get_direct_video_url(CUSTOM_MEDIA_URL)
        if video_direct:
            path = process_video(video_direct, 0)
            if path:
                paths_to_send.append(path)
                titulos.append("Mídia Exclusiva")
    elif TARGET_URL:
        links = [TARGET_URL] if "/video." in TARGET_URL else []
        if not links:
            try:
                res = scraper.get(TARGET_URL, timeout=20)
                soup = BeautifulSoup(res.text, 'html.parser')
                for a in soup.select('p.title a'): links.append(f"https://www.xvideos.com{a['href']}")
            except: pass

        for i, url in enumerate(links):
            if len(paths_to_send) >= SCRAPE_LIMIT: break
            video_direct = get_direct_video_url(url)
            if video_direct:
                path = process_video(video_direct, i)
                if path:
                    paths_to_send.append(path)
                    try:
                        res_title = scraper.get(url, timeout=10)
                        soup_title = BeautifulSoup(res_title.text, 'html.parser')
                        title_original = soup_title.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
                        titulos.append(traduzir_para_pt(title_original))
                    except:
                        titulos.append("Conteúdo Premium")

    # Disparo
    if paths_to_send:
        print(f"📦 Enviando para o Telegram (Modo: {SEND_MODE})...", flush=True)
        if SEND_MODE == 'gallery':
            send_gallery_mode(paths_to_send, titulos[0] if titulos else "")
        else:
            send_single_mode(paths_to_send, titulos)
            
        for p in paths_to_send:
            if os.path.exists(p): os.remove(p)
    else:
        print("❌ Nenhuma mídia processada.", flush=True)
