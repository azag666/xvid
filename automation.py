import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
DEFAULT_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

config_data_str = os.environ.get('CONFIG_DATA', '{}')
try:
    config = json.loads(config_data_str)
except:
    config = {}

CHAT_ID = config.get('chat_id', '').strip() or DEFAULT_CHAT_ID
TARGET_URL = config.get('video_url', '').strip()
CUSTOM_MEDIA_URL = config.get('custom_media_url', '').strip()

SCRAPE_LIMIT = int(config.get('scrape_limit', 5))
VIDEO_DURATION = config.get('video_duration', 'teaser')
WATERMARK_TEXT = config.get('watermark_text', '').strip()
WATERMARK_POS = config.get('watermark_pos', 'bottom_right')
WATERMARK_SIZE = config.get('watermark_size', '28')

USE_SPOILER = config.get('use_spoiler', True)
USE_TITLE = config.get('use_title', True)
SEND_MODE = config.get('send_mode', 'single')

CUSTOM_CAPTION = config.get('caption_text', '')
BOTOES_LISTA = config.get('dynamic_buttons', [])

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
    print(f"🕵️ Extraindo link de: {page_url}", flush=True)
    cmd = ['yt-dlp', '-g', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', page_url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        url = result.stdout.strip()
        if url: 
            return url
        else:
            print(f"⚠️ Erro ao extrair (yt-dlp vazio): {result.stderr}", flush=True)
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}", flush=True)
    return None

def process_media(input_url, index, is_image=False):
    timestamp = int(time.time())
    
    if is_image:
        temp_img = f"temp_{index}_{timestamp}.jpg"
        out_img = f"media_{index}_{timestamp}.jpg"
        print(f"📸 Baixando imagem {index}...", flush=True)
        try:
            r = requests.get(input_url, timeout=15)
            r.raise_for_status()
            with open(temp_img, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"❌ Erro ao baixar imagem: {e}", flush=True)
            return None
        
        cmd = ['ffmpeg', '-y', '-i', temp_img]
        if WATERMARK_TEXT:
            escaped_text = WATERMARK_TEXT.replace("'", "\\'")
            if WATERMARK_POS == 'top_left': pos = 'x=15:y=15'
            elif WATERMARK_POS == 'top_right': pos = 'x=w-tw-15:y=15'
            elif WATERMARK_POS == 'bottom_left': pos = 'x=15:y=h-th-15'
            elif WATERMARK_POS == 'center': pos = 'x=(w-tw)/2:y=(h-th)/2'
            else: pos = 'x=w-tw-15:y=h-th-15'
            vf_filter = f"drawtext=text='{escaped_text}':fontcolor=white:fontsize={WATERMARK_SIZE}:box=1:boxcolor=black@0.6:{pos}"
            cmd.extend(['-vf', vf_filter])
        cmd.append(out_img)
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            if os.path.exists(temp_img): os.remove(temp_img)
            return (out_img, 'photo')
        except Exception as e:
            print(f"❌ Erro ao processar imagem no FFmpeg: {e}", flush=True)
            return None

    else:
        out_vid = f"media_{index}_{timestamp}.mp4"
        print(f"🎬 Processando vídeo {index}...", flush=True)
        cmd = ['ffmpeg', '-y']
        if VIDEO_DURATION == 'teaser': cmd.extend(['-ss', '00:00:05', '-t', '15'])
        cmd.extend(['-i', input_url])
        
        if WATERMARK_TEXT:
            escaped_text = WATERMARK_TEXT.replace("'", "\\'")
            if WATERMARK_POS == 'top_left': pos = 'x=15:y=15'
            elif WATERMARK_POS == 'top_right': pos = 'x=w-tw-15:y=15'
            elif WATERMARK_POS == 'bottom_left': pos = 'x=15:y=h-th-15'
            elif WATERMARK_POS == 'center': pos = 'x=(w-tw)/2:y=(h-th)/2'
            else: pos = 'x=w-tw-15:y=h-th-15'
            vf_filter = f"drawtext=text='{escaped_text}':fontcolor=white:fontsize={WATERMARK_SIZE}:box=1:boxcolor=black@0.6:{pos}"
            cmd.extend(['-vf', vf_filter])
            
        cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', '-c:a', 'aac', '-b:a', '64k', out_vid])
        
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            return (out_vid, 'video')
        except Exception as e:
            print(f"❌ Erro FFmpeg vídeo: {e}", flush=True)
        return None

def build_reply_markup():
    inline_keyboard = []
    try:
        for b in BOTOES_LISTA:
            inline_keyboard.append([{"text": b['name'], "url": b['url']}])
    except: pass
    return json.dumps({"inline_keyboard": inline_keyboard}) if inline_keyboard else None

def build_caption(titulo_pt, only_title=False, only_copy_and_call=False):
    cap = ""
    # Modo Galeria: Apenas Título no Vídeo
    if only_title:
        if USE_TITLE and titulo_pt: cap += f"🔞 <b>{titulo_pt}</b>"
        return cap.strip()
        
    # Modo Galeria: Apenas Copy
    if only_copy_and_call:
        if CUSTOM_CAPTION: cap += f"{CUSTOM_CAPTION}"
        return cap.strip()
        
    # Modo Single: Título e Copy
    if USE_TITLE and titulo_pt: cap += f"🔞 <b>{titulo_pt}</b>\n\n"
    if CUSTOM_CAPTION: cap += f"{CUSTOM_CAPTION}"
    
    return cap.strip()

def send_gallery_mode(media_items, titulo_pt):
    media_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    media_group = []
    files = {}
    
    for i, (path, mtype) in enumerate(media_items):
        legenda = build_caption(titulo_pt, only_title=True) if i == 0 else ""
        media_group.append({
            'type': mtype, 
            'media': f'attach://file{i}', 
            'has_spoiler': USE_SPOILER, 
            'caption': legenda, 
            'parse_mode': 'HTML'
        })
        files[f'file{i}'] = open(path, 'rb')
        
    try:
        res = requests.post(media_url, data={'chat_id': CHAT_ID, 'media': json.dumps(media_group)}, files=files, timeout=120)
        if not res.json().get('ok'):
            print(f"❌ Erro na Galeria: {res.text}", flush=True)
    finally:
        for f in files.values(): f.close()

    # Enviar a mensagem separada apenas se houver Copy Principal OU Botões
    text_to_send = build_caption(titulo_pt, only_copy_and_call=True)
    reply_markup = build_reply_markup()
    
    if text_to_send or reply_markup:
        msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        # Se tem botões mas não tem texto, insere um caractere invisível ou genérico para a API do Telegram não dar erro de mensagem vazia
        payload_msg = { 
            'chat_id': CHAT_ID, 
            'text': text_to_send if text_to_send else "👇", 
            'parse_mode': 'HTML' 
        }
        if reply_markup: 
            payload_msg['reply_markup'] = reply_markup
        requests.post(msg_url, data=payload_msg, timeout=30)
        
    return True

def send_single_mode(media_items, titulos):
    reply_markup = build_reply_markup()
    
    for i, (path, mtype) in enumerate(media_items):
        titulo_atual = titulos[i] if len(titulos) > i else "Conteúdo Premium"
        caption = build_caption(titulo_atual)
        
        api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if mtype == 'photo' else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        file_key = 'photo' if mtype == 'photo' else 'video'
        
        payload = {
            'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML',
            'has_spoiler': str(USE_SPOILER).lower()
        }
        if mtype == 'video': payload['supports_streaming'] = 'true'
        if reply_markup: payload['reply_markup'] = reply_markup
        
        try:
            with open(path, 'rb') as f:
                res = requests.post(api_url, data=payload, files={file_key: f}, timeout=60)
                if not res.json().get('ok'):
                    print(f"❌ Erro no envio ({mtype}): {res.text}", flush=True)
            time.sleep(3)
        except Exception as e:
            print(f"❌ Erro no envio individual: {e}", flush=True)
    return True

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID: 
        print("❌ ERRO: Faltam credenciais do Telegram.", flush=True)
        sys.exit(1)

    media_to_send = []
    titulos = []

    if CUSTOM_MEDIA_URL:
        is_img = any(CUSTOM_MEDIA_URL.lower().split('?')[0].endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif'])
        
        if is_img:
            result = process_media(CUSTOM_MEDIA_URL, 0, is_image=True)
            if result:
                media_to_send.append(result)
                titulos.append("Imagem Exclusiva")
        else:
            video_direct = get_direct_video_url(CUSTOM_MEDIA_URL)
            if video_direct:
                result = process_media(video_direct, 0, is_image=False)
                if result:
                    media_to_send.append(result)
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
            if len(media_to_send) >= SCRAPE_LIMIT: break
            video_direct = get_direct_video_url(url)
            if video_direct:
                result = process_media(video_direct, i, is_image=False)
                if result:
                    media_to_send.append(result)
                    try:
                        res_title = scraper.get(url, timeout=10)
                        soup_title = BeautifulSoup(res_title.text, 'html.parser')
                        title_original = soup_title.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
                        titulos.append(traduzir_para_pt(title_original))
                    except:
                        titulos.append("Conteúdo Premium")

    if media_to_send:
        print(f"📦 Enviando para o Telegram (Modo: {SEND_MODE})...", flush=True)
        if SEND_MODE == 'gallery':
            send_gallery_mode(media_to_send, titulos[0] if titulos else "")
        else:
            send_single_mode(media_to_send, titulos)
            
        for p, mtype in media_to_send:
            if os.path.exists(p): os.remove(p)
    else:
        print("❌ Nenhuma mídia processada.", flush=True)
