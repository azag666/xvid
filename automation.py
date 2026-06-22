import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

# 1. CAPTURA DE VARIÁVEIS DE AMBIENTE
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Origem
TARGET_URL = os.environ.get('TARGET_URL', '').strip()
CUSTOM_MEDIA_URL = os.environ.get('CUSTOM_MEDIA_URL', '').strip()

# Configurações de Edição
SCRAPE_LIMIT = int(os.environ.get('SCRAPE_LIMIT', '5') or '5')
VIDEO_DURATION = os.environ.get('VIDEO_DURATION', 'teaser')
WATERMARK_TEXT = os.environ.get('WATERMARK_TEXT', '').strip()

# Mensagem
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')
RAW_BUTTONS = os.environ.get('DYNAMIC_BUTTONS', '[]')

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def traduzir_para_pt(texto):
    try:
        texto_seguro = urllib.parse.quote(texto)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=pt&dt=t&q={texto_seguro}"
        res = requests.get(url, timeout=5)
        return res.json()[0][0][0]
    except:
        return texto

def get_direct_video_url(page_url):
    print(f"🕵️ Extraindo link direto de: {page_url}", flush=True)
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
    print(f"🎬 Processando vídeo {index} (Modo: {VIDEO_DURATION})...", flush=True)
    
    cmd = ['ffmpeg', '-y']
    
    # Se for teaser, corta os primeiros 5s e filma 15s. Se não, processa inteiro.
    if VIDEO_DURATION == 'teaser':
        cmd.extend(['-ss', '00:00:05', '-t', '15'])
        
    cmd.extend(['-i', video_direct_url])
    
    # Aplica Marca D'água se fornecida (Texto branco, fundo semitransparente, margem inferior direita)
    if WATERMARK_TEXT:
        escaped_text = WATERMARK_TEXT.replace("'", "\\'")
        vf_filter = f"drawtext=text='{escaped_text}':fontcolor=white:fontsize=28:box=1:boxcolor=black@0.6:x=w-tw-15:y=h-th-15"
        cmd.extend(['-vf', vf_filter])
        
    cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', '-c:a', 'aac', '-b:a', '64k', output_file])
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300) # 5 minutos max para vídeos completos
        return output_file if os.path.exists(output_file) else None
    except Exception as e:
        print(f"❌ Erro FFmpeg: {e}", flush=True)
    return None

def send_gallery_and_buttons(paths, titulo_pt):
    # 1. GALERIA
    media_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    media_group = []
    files = {}
    
    for i, path in enumerate(paths):
        legenda = f"🔞 <b>{titulo_pt}</b>" if i == 0 else ""
        media_group.append({
            'type': 'video',
            'media': f'attach://video{i}',
            'has_spoiler': True,
            'caption': legenda,
            'parse_mode': 'HTML'
        })
        files[f'video{i}'] = open(path, 'rb')
        
    try:
        res_media = requests.post(media_url, data={'chat_id': CHAT_ID, 'media': json.dumps(media_group)}, files=files, timeout=120)
        if not res_media.json().get('ok'):
            print(f"❌ Erro Galeria: {res_media.text}", flush=True)
            return False
    finally:
        for f in files.values():
            f.close()

    # 2. MENSAGEM COM BOTÕES DINÂMICOS
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    caption_botoes = f"{CUSTOM_CAPTION}\n\n👇 <b>ESCOLHA SUA OPÇÃO:</b> 👇"
    
    # Processar o JSON de botões vindo do Front-end
    inline_keyboard = []
    try:
        botoes_lista = json.loads(RAW_BUTTONS)
        for b in botoes_lista:
            inline_keyboard.append([{"text": b['name'], "url": b['url']}])
    except:
        pass # Se falhar, vai sem botões
        
    payload_msg = {
        'chat_id': CHAT_ID,
        'text': caption_botoes,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps({"inline_keyboard": inline_keyboard})
    }
    
    try:
        res_msg = requests.post(msg_url, data=payload_msg, timeout=30)
        return res_msg.json().get('ok')
    except Exception as e:
        print(f"❌ Erro Botões: {e}", flush=True)
        return False

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ ERRO: Faltam credenciais do Telegram.", flush=True)
        sys.exit(1)

    paths_to_send = []
    titulo_principal = "Conteúdo Premium"

    # LÓGICA DE DECISÃO: Mídia Própria vs Scraping
    if CUSTOM_MEDIA_URL:
        print(f"🚀 Iniciando processamento de MÍDIA PRÓPRIA...", flush=True)
        video_direct = get_direct_video_url(CUSTOM_MEDIA_URL)
        if video_direct:
            path = process_video(video_direct, 0)
            if path:
                paths_to_send.append(path)
    
    elif TARGET_URL:
        print(f"🚀 Iniciando SCRAPING... Alvo: {TARGET_URL}", flush=True)
        links = []
        if "/video." in TARGET_URL:
            links = [TARGET_URL]
        else:
            try:
                res = scraper.get(TARGET_URL, timeout=20)
                soup = BeautifulSoup(res.text, 'html.parser')
                for a in soup.select('p.title a'):
                    links.append(f"https://www.xvideos.com{a['href']}")
            except Exception as e:
                print(f"❌ Erro no Scraping: {e}", flush=True)

        for i, url in enumerate(links):
            if len(paths_to_send) >= SCRAPE_LIMIT:
                break
                
            video_direct = get_direct_video_url(url)
            if video_direct:
                path = process_video(video_direct, i)
                if path:
                    paths_to_send.append(path)
                    if len(paths_to_send) == 1:
                        try:
                            res_title = scraper.get(url, timeout=10)
                            soup_title = BeautifulSoup(res_title.text, 'html.parser')
                            title_original = soup_title.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
                            titulo_principal = traduzir_para_pt(title_original)
                        except: pass

    # DISPARO
    if paths_to_send:
        print(f"📦 Enviando para o Telegram...", flush=True)
        sucesso = send_gallery_and_buttons(paths_to_send, titulo_principal)
        if sucesso:
            print("✅ Sucesso Total!", flush=True)
        
        # Limpeza
        for p in paths_to_send:
            if os.path.exists(p): os.remove(p)
    else:
        print("❌ Nenhuma mídia processada.", flush=True)
