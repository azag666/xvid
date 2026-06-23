import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
import random
from bs4 import BeautifulSoup
import urllib.parse

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
DEFAULT_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

config_data_str = os.environ.get('CONFIG_DATA', '{}')
try:
    config = json.loads(config_data_str) if config_data_str else {}
except:
    config = {}

# ==========================================
# 🧠 BANCO DE DADOS AUTOMÁTICO (PILOTO 24/7)
# Se o robô rodar sozinho pelo agendador, ele usa estes dados:
# ==========================================
LINK_ALVO_AUTOMATICO = "https://www.xvideos.com/tags/amadoras"

COPYS_AUTOMATICAS = [
    "📱 Cansei de intermediários. Quero você no meu WhatsApp pessoal hoje! Me chama lá para chamadas de vídeo e +30 vídeos exclusivos que só libero no privado. R$ 15,00 entrada única! 😈👇",
    "🔥 Você quer me ver de verdade? Liberei meu número particular! Vem trocar mensagens comigo, fazer chamada de vídeo e ainda ganha mais de 30 vídeos meus sem censura. Clica aqui: 🔞",
    "🚨 ATENÇÃO: Meu WhatsApp pessoal tá liberado por alguns minutos. Quem entrar agora vai fazer chamada de vídeo comigo e receber +30 vídeos que nunca postei em lugar nenhum! 💦👇",
    "👀 Quer me ver ao vivo? Pega meu WhatsApp pessoal hoje. Além de chamada de vídeo, separei um pack com mais de 30 vídeos ultra exclusivos direto no seu zap por R$ 15,00! 💵",
    "🤫 Chega de robô, eu quero falar com você direto no meu celular. Garanta meu número privado, faz chamada de vídeo comigo e racha de ver meus +30 vídeos proibidos agora! 👇",
    "😈 Se você aguenta conteúdo pesado, me chama no WhatsApp pessoal. São mais de 30 vídeos exclusivos e direito a chamada de vídeo comigo no sigilo. Só R$ 15,00 hoje! 📞",
    "💥 Acabei de liberar meu número real! Quero te mandar mais de 30 vídeos exclusivos direto no seu zap e te atender em chamada de vídeo. Não perde tempo e clica abaixo! 🏃‍♀️💨",
    "❌ Não compre se não aguentar safadeza amadora. Meu WhatsApp pessoal tá aberto: +30 vídeos secretos inclusos e tô online para chamada de vídeo. Vem antes que eu mude de número! 🔒",
    "❤️ Quero intimidade com você. Por R$ 15,00 você pega meu WhatsApp particular, ganha acesso a chamadas de vídeo comigo e destrava mais de 30 vídeos meus mais quentes! 👅👇",
    "📱 Meu WhatsApp pessoal tá na sua mão. Quer me ver por chamada de vídeo e receber +30 vídeos que o bot não mostra? Taxa única de R$ 15,00. Clica e me chama agora! 👇",
    "🔥 O que eu posto aqui não é nada perto do que te envio no privado. Garanta meu WhatsApp pessoal, faz chamada de vídeo comigo e assista a mais de 30 vídeos exclusivos meus! 🔞",
    "🚨 LINK EXCLUSIVO: Saia do bot e venha falar direto comigo no meu celular. Te entrego +30 vídeos inéditos e te atendo em chamada de vídeo por apenas R$ 15,00! ⚡👇",
    "🤤 Quer me ver do jeito que vim ao mundo? Pega meu WhatsApp pessoal agora! Tem chamada de vídeo ao vivo e mais de 30 mídias exclusivas te esperando na conversa. Clica já! 💳",
    "🤫 Meu contato privado sumirá em 2 minutos. Garanta meu WhatsApp pessoal por R$ 15,00: faça chamada de vídeo e receba mais de 30 vídeos que ninguém mais tem acesso! 🔥",
    "🔞 Quer falar comigo sem censura? Liberei meu WhatsApp pessoal só para os primeiros. Vem fazer chamada de vídeo e receber +30 vídeos meus totalmente privados. Clica abaixo! 👇"
]

BOTOES_AUTOMATICOS = [
    {"name": "📱 WhatsApp Pessoal (R$ 15)", "url": "https://whatspessoalvitoria.netlify.app"},
]
# ==========================================

# Se vier do Painel, usa o do Painel. Se não, usa os automáticos.
CHAT_ID = config.get('chat_id', '').strip() or DEFAULT_CHAT_ID
TARGET_URL = config.get('video_url', '').strip() or LINK_ALVO_AUTOMATICO
CUSTOM_MEDIA_URL = config.get('custom_media_url', '').strip()

SCRAPE_LIMIT = int(config.get('scrape_limit', 5))
VIDEO_DURATION = config.get('video_duration', 'teaser')
WATERMARK_TEXT = config.get('watermark_text', '').strip()
WATERMARK_POS = config.get('watermark_pos', 'bottom_right')
WATERMARK_SIZE = config.get('watermark_size', '28')

USE_SPOILER = config.get('use_spoiler', True)
USE_TITLE = config.get('use_title', True)
SEND_MODE = config.get('send_mode', 'single')

# Sorteia uma copy se estiver vazio (rodando no modo automático 24h)
CUSTOM_CAPTION = config.get('caption_text', '')
if not CUSTOM_CAPTION and not config:
    CUSTOM_CAPTION = random.choice(COPYS_AUTOMATICAS)

BOTOES_LISTA = config.get('dynamic_buttons', [])
if not BOTOES_LISTA and not config:
    BOTOES_LISTA = BOTOES_AUTOMATICOS

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
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}", flush=True)
    return None

def process_media(input_url, index, is_image=False):
    timestamp = int(time.time())
    
    if is_image:
        temp_img = f"temp_{index}_{timestamp}.jpg"
        out_img = f"media_{index}_{timestamp}.jpg"
        try:
            r = requests.get(input_url, timeout=15)
            r.raise_for_status()
            with open(temp_img, 'wb') as f: f.write(r.content)
        except Exception as e: return None
        
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
        except Exception: return None

    else:
        out_vid = f"media_{index}_{timestamp}.mp4"
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
        except Exception: return None

def build_reply_markup():
    inline_keyboard = []
    try:
        for b in BOTOES_LISTA:
            inline_keyboard.append([{"text": b['name'], "url": b['url']}])
    except: pass
    return json.dumps({"inline_keyboard": inline_keyboard}) if inline_keyboard else None

def build_caption(titulo_pt, only_title=False, only_copy_and_call=False):
    cap = ""
    if only_title:
        if USE_TITLE and titulo_pt: cap += f"🔞 <b>{titulo_pt}</b>"
        return cap.strip()
        
    if only_copy_and_call:
        if CUSTOM_CAPTION: cap += f"{CUSTOM_CAPTION}"
        return cap.strip()
        
    if USE_TITLE and titulo_pt: cap += f"🔞 <b>{titulo_pt}</b>\n\n"
    if CUSTOM_CAPTION: cap += f"{CUSTOM_CAPTION}"
    
    return cap.strip()

def send_gallery_mode(media_items, titulo_pt):
    media_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    media_group = []
    files = {}
    
    for i, (path, mtype) in enumerate(media_items):
        legenda = build_caption(titulo_pt, only_title=True) if i == 0 else ""
        media_group.append({'type': mtype, 'media': f'attach://file{i}', 'has_spoiler': USE_SPOILER, 'caption': legenda, 'parse_mode': 'HTML'})
        files[f'file{i}'] = open(path, 'rb')
        
    try:
        requests.post(media_url, data={'chat_id': CHAT_ID, 'media': json.dumps(media_group)}, files=files, timeout=120)
    finally:
        for f in files.values(): f.close()

    text_to_send = build_caption(titulo_pt, only_copy_and_call=True)
    reply_markup = build_reply_markup()
    
    if text_to_send or reply_markup:
        msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload_msg = { 'chat_id': CHAT_ID, 'text': text_to_send if text_to_send else "👇", 'parse_mode': 'HTML' }
        if reply_markup: payload_msg['reply_markup'] = reply_markup
        requests.post(msg_url, data=payload_msg, timeout=30)
    return True

def send_single_mode(media_items, titulos):
    reply_markup = build_reply_markup()
    for i, (path, mtype) in enumerate(media_items):
        titulo_atual = titulos[i] if len(titulos) > i else "Conteúdo Premium"
        caption = build_caption(titulo_atual)
        api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if mtype == 'photo' else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
        file_key = 'photo' if mtype == 'photo' else 'video'
        
        payload = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML', 'has_spoiler': str(USE_SPOILER).lower()}
        if mtype == 'video': payload['supports_streaming'] = 'true'
        if reply_markup: payload['reply_markup'] = reply_markup
        
        try:
            with open(path, 'rb') as f: requests.post(api_url, data=payload, files={file_key: f}, timeout=60)
            time.sleep(3)
        except Exception: pass
    return True

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID: sys.exit(1)

    media_to_send = []
    titulos = []

    if CUSTOM_MEDIA_URL:
        is_img = any(CUSTOM_MEDIA_URL.lower().split('?')[0].endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif'])
        result = process_media(CUSTOM_MEDIA_URL, 0, is_image=is_img)
        if result:
            media_to_send.append(result)
            titulos.append("Conteúdo Exclusivo")
                    
    elif TARGET_URL:
        # Se for rodar automático 24h, sorteia uma página aleatória do XV para não repetir vídeos
        final_url = TARGET_URL
        if not config and "/tags/" in TARGET_URL:
            pagina_random = random.randint(1, 15)
            final_url = f"{TARGET_URL}/{pagina_random}"
            print(f"🤖 Modo Automático 24/7 Ativado. Raspando página {pagina_random}...")

        links = [final_url] if "/video." in final_url else []
        if not links:
            try:
                res = scraper.get(final_url, timeout=20)
                soup = BeautifulSoup(res.text, 'html.parser')
                for a in soup.select('p.title a'): links.append(f"https://www.xvideos.com{a['href']}")
            except: pass

        if len(links) > SCRAPE_LIMIT:
            links = random.sample(links, SCRAPE_LIMIT)

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
        print(f"📦 Enviando para o Telegram...", flush=True)
        if SEND_MODE == 'gallery': send_gallery_mode(media_to_send, titulos[0] if titulos else "")
        else: send_single_mode(media_to_send, titulos)
            
        for p, mtype in media_to_send:
            if os.path.exists(p): os.remove(p)
