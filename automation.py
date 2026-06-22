import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

# Recebendo os parâmetros dinâmicos do GitHub Actions
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')

# Links dos botões recebidos do front-end
LINK_WHATSAPP = os.environ.get('LINK_WHATSAPP', 'https://t.me/default')
LINK_AMIGAS = os.environ.get('LINK_AMIGAS', 'https://t.me/default')
LINK_CHAMADA = os.environ.get('LINK_CHAMADA', 'https://t.me/default')

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def traduzir_para_pt(texto):
    try:
        texto_seguro = urllib.parse.quote(texto)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=pt&dt=t&q={texto_seguro}"
        resposta = requests.get(url, timeout=5)
        return resposta.json()[0][0][0]
    except Exception as e:
        print(f"⚠️ Aviso (Tradução falhou): {e}", flush=True)
        return texto

def get_direct_video_url(page_url):
    print(f"🕵️ Extraindo link: {page_url}", flush=True)
    cmd = ['yt-dlp', '-g', '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', page_url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        url = result.stdout.strip()
        if url: return url
    except Exception as e:
        print(f"❌ Erro yt-dlp: {e}", flush=True)
    return None

def generate_snippet(video_direct_url, index):
    output_file = f"video_{index}_{int(time.time())}.mp4"
    print(f"✂️ Criando teaser rápido {index}...", flush=True)
    cmd = [
        'ffmpeg', '-y', '-ss', '00:00:05', '-t', '15', # Reduzido para 15s para processar 5 vídeos mais rápido
        '-i', video_direct_url, 
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', 
        '-c:a', 'aac', '-b:a', '64k', output_file
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        return output_file if os.path.exists(output_file) else None
    except Exception as e:
        print(f"❌ Erro FFmpeg: {e}", flush=True)
    return None

def send_gallery_and_buttons(paths, titulo_pt):
    # 1. ENVIAR GALERIA (MEDIA GROUP) COM SPOILER
    media_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    
    media_group = []
    files = {}
    
    for i, path in enumerate(paths):
        # Apenas a primeira mídia carrega o título
        legenda = f"🔞 <b>{titulo_pt}</b>" if i == 0 else ""
        
        media_group.append({
            'type': 'video',
            'media': f'attach://video{i}',
            'has_spoiler': True, # ISTO ATIVA O EFEITO DESFOCADO
            'caption': legenda,
            'parse_mode': 'HTML'
        })
        files[f'video{i}'] = open(path, 'rb')
        
    payload_media = {
        'chat_id': CHAT_ID,
        'media': json.dumps(media_group)
    }
    
    try:
        res_media = requests.post(media_url, data=payload_media, files=files, timeout=120)
        if not res_media.json().get('ok'):
            print(f"❌ Erro ao enviar galeria: {res_media.text}", flush=True)
            return False
    except Exception as e:
        print(f"❌ Erro de requisição na galeria: {e}", flush=True)
        return False
    finally:
        # Fechar arquivos para permitir exclusão
        for f in files.values():
            f.close()

    # 2. ENVIAR A MENSAGEM COM CTA E BOTÕES SEPARADAMENTE
    msg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    caption_botoes = (
        f"🔥 <b>ACESSO EXCLUSIVO:</b>\n"
        f"{CUSTOM_CAPTION}\n\n"
        f"👇 <b>ESCOLHA A SUA OPÇÃO ABAIXO:</b> 👇"
    )
    
    reply_markup = {
        "inline_keyboard": [
            [{"text": "📱 WhatsApp Pessoa (R$ 15,00)", "url": LINK_WHATSAPP}],
            [{"text": "👯‍♀️ Amigas (R$ 15,00)", "url": LINK_AMIGAS}],
            [{"text": "📹 Chamada de Vídeo (R$ 45,00)", "url": LINK_CHAMADA}]
        ]
    }
    
    payload_msg = {
        'chat_id': CHAT_ID,
        'text': caption_botoes,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps(reply_markup)
    }
    
    try:
        res_msg = requests.post(msg_url, data=payload_msg, timeout=30)
        return res_msg.json().get('ok')
    except Exception as e:
        print(f"❌ Erro ao enviar botões: {e}", flush=True)
        return False

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID or not TARGET_URL:
        print("❌ ERRO: Faltam configurações essenciais.", flush=True)
        sys.exit(1)

    print(f"🚀 Sniper Engine Multi-Vídeo - Alvo: {TARGET_URL} | Grupo: {CHAT_ID}", flush=True)
    
    links = []
    # Se for um link direto de vídeo, tenta processar só ele (não formará uma galeria grande)
    if "/video." in TARGET_URL:
        links = [TARGET_URL]
    else:
        # Se for categoria, raspa os vídeos
        try:
            res = scraper.get(TARGET_URL, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.select('p.title a'):
                links.append(f"https://www.xvideos.com{a['href']}")
        except Exception as e:
            print(f"❌ Erro no Scraping: {e}", flush=True)

    paths_to_send = []
    titulo_principal = "Conteúdo Premium Exclusivo"

    print(f"🎯 Extraindo até 5 vídeos de uma fila de {len(links)}...", flush=True)

    for i, url in enumerate(links):
        if len(paths_to_send) >= 5: # Limite de 5 vídeos para a galeria
            break
            
        video_direct = get_direct_video_url(url)
        if video_direct:
            path = generate_snippet(video_direct, i)
            if path:
                paths_to_send.append(path)
                
                # Extrai o título do primeiro vídeo capturado para ser o título da postagem
                if len(paths_to_send) == 1:
                    try:
                        res_title = scraper.get(url, timeout=10)
                        soup_title = BeautifulSoup(res_title.text, 'html.parser')
                        title_original = soup_title.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
                        titulo_principal = traduzir_para_pt(title_original)
                    except:
                        pass

    # Dispara a galeria se conseguiu capturar as mídias
    if paths_to_send:
        print(f"📦 Enviando Galeria com {len(paths_to_send)} vídeos (Spoiler ATIVADO)...", flush=True)
        
        sucesso = send_gallery_and_buttons(paths_to_send, titulo_principal)
        
        if sucesso:
            print("✅ Galeria e botões postados com sucesso no grupo!", flush=True)
        
        # Limpeza de disco
        for p in paths_to_send:
            if os.path.exists(p): 
                os.remove(p)
    else:
        print("❌ Nenhum vídeo pôde ser extraído e processado.", flush=True)
