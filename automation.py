import os
import sys
import time
import requests
import json
import re
import subprocess

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS ---
def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except:
        pass

# Garante que o motor de extração esteja presente
try:
    import yt_dlp
except ImportError:
    install_package("yt-dlp")
    import yt_dlp

# Garante que o simulador de navegador esteja presente
try:
    import cloudscraper
except ImportError:
    install_package("cloudscraper")
    import cloudscraper

from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES DO SISTEMA ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')
BUTTON_LINK = os.environ.get('BUTTON_LINK') # Link de Checkout/Venda configurado no painel

# Inicializa o scraper com perfil de navegador real
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

# Headers para simular tráfego humano e forçar idioma PT-BR
HEADERS_PT = {
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def check_ffmpeg():
    """Verifica se o FFmpeg está instalado, essencial para os recortes."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("⚠️ FFmpeg não encontrado no ambiente. Tentando instalação manual...")
        try:
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', 'ffmpeg', '-y'], check=True)
            return True
        except:
            return False

def get_direct_video_url(page_url):
    """Extrai o link direto do arquivo de vídeo usando yt-dlp."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
        'socket_timeout': 30,
        'user_agent': HEADERS_PT['User-Agent'],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
            return info.get('url')
    except Exception as e:
        print(f"⚠️ Erro na extração do link direto: {e}")
        return None

def generate_snippet(video_direct_url, duration=3):
    """Gera um recorte de 3 segundos focado em conversão."""
    output_file = f"snippet_{int(time.time())}.mp4"
    print(f"✂️ Gerando preview de {duration}s...")
    
    # Comando FFmpeg otimizado para velocidade 'ultrafast'
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-headers', f'User-Agent: {HEADERS_PT["User-Agent"]}\r\nReferer: https://www.xvideos.com/\r\n',
        '-ss', '00:00:15', # Pula o início para pegar uma cena de impacto
        '-t', str(duration),
        '-i', video_direct_url,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32',
        '-c:a', 'aac', '-b:a', '64k',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_file
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            return output_file
    except Exception as e:
        print(f"⚠️ Falha no processamento do vídeo: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    return None

def send_to_telegram(data):
    """Envia o vídeo para o Telegram com botões de venda configurados."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    
    # Legenda 100% Stealth (sem links externos, título limpo)
    caption = f"🔞 <b>{data['titulo']}</b>\n\n"
    if CUSTOM_CAPTION:
        caption += f"💎 {CUSTOM_CAPTION}\n\n"
    else:
        caption += "🔥 <b>CONTEÚDO COMPLETO DISPONÍVEL!</b>\n"
        caption += "🚀 Assista agora sem censura e em 4K.\n\n"
    
    caption += "👇 <b>LIBERE O ACESSO ABAIXO:</b>"

    # Botões direcionando APENAS para o link de checkout configurado no painel
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔓 LIBERAR VÍDEO (PIX)", "url": BUTTON_LINK}],
            [{"text": "⭐ PACK VITALÍCIO - R$ 19,99", "url": BUTTON_LINK}]
        ]
    }

    try:
        with open(data['path'], 'rb') as f:
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML',
                'supports_streaming': 'true',
                'reply_markup': json.dumps(reply_markup)
            }
            r = requests.post(api_url, data=payload, files={'video': f}, timeout=150)
            res = r.json()
            if not res.get('ok'):
                print(f"❌ Erro API Telegram: {res.get('description')}")
        
        # Limpeza do arquivo local
        os.remove(data['path'])
    except Exception as e:
        print(f"❌ Erro no envio: {e}")

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL, BUTTON_LINK]):
        print("❌ Faltam configurações (Token, Chat ID, URL ou Link de Checkout).")
        sys.exit(1)

    if not check_ffmpeg():
        print("❌ FFmpeg é obrigatório para gerar recortes.")
        sys.exit(1)

    print("--- SNIPER ENGINE V3.5 ATIVADA ---")
    
    links = []
    try:
        # Tenta carregar listagem de vídeos (Scrapping de Massa)
        r = scraper.get(TARGET_URL, headers=HEADERS_PT, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        
        for b in blocks:
            if len(links) >= 15: break # Limite de 15 vídeos por disparo
            try:
                link_tag = b.find('p', class_='title').find('a')
                links.append(f"https://www.xvideos.com{link_tag['href']}")
            except: continue
    except:
        # Se falhar a listagem, assume que o link é um vídeo único
        links = [TARGET_URL]

    if not links:
        print("⚠️ Nenhum vídeo encontrado para processar.")
        sys.exit(1)

    print(f"🎯 Total de vídeos para converter: {len(links)}")

    for link in links:
        try:
            # Captura o título antes para a legenda
            r_video = scraper.get(link, headers=HEADERS_PT, timeout=15)
            soup_video = BeautifulSoup(r_video.text, 'html.parser')
            title = soup_video.find("meta", property="og:title")["content"]
            title = title.replace(" - XVIDEOS.COM", "").strip()

            v_url = get_direct_video_url(link)
            if v_url:
                video_path = generate_snippet(v_url, duration=3) # Recorte de 3 segundos
                if video_path:
                    send_to_telegram({"path": video_path, "titulo": title})
                    print(f"✅ Sucesso: {title}")
                    time.sleep(12) # Intervalo anti-spam
                else:
                    print(f"⏭️ Falha no recorte: {title}")
            else:
                print(f"⏭️ Não foi possível obter stream de: {link}")
        except Exception as e:
            print(f"⚠️ Erro ao processar item: {e}")
            continue

    print("--- OPERAÇÃO FINALIZADA ---")
