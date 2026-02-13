import os
import sys
import time
import requests
import json
import re
import subprocess

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS CRÍTICAS ---
def install_package(package):
    try:
        print(f"⬇️ A instalar {package} automaticamente...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"❌ Erro ao instalar {package}: {e}")

# Garante que o yt-dlp (extrator de vídeo) está presente
try:
    import yt_dlp
except ImportError:
    install_package("yt-dlp")
    import yt_dlp

# Garante que o cloudscraper (burlar proteções) está presente
try:
    import cloudscraper
except ImportError:
    install_package("cloudscraper")
    import cloudscraper

from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES DO SISTEMA ---
# Estas variáveis são passadas pelo GitHub Actions (disparo.yml)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')
BUTTON_LINK = os.environ.get('BUTTON_LINK') # Teu link de checkout/venda

# Inicializa o scraper simulando um navegador real
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

# Cabeçalhos para simular tráfego humano e forçar idioma em Português
HEADERS_PT = {
    'Accept-Language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def check_ffmpeg():
    """Verifica se o FFmpeg está disponível no sistema."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        print("⚠️ FFmpeg não encontrado. A tentar instalar via apt-get...")
        try:
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', 'ffmpeg', '-y'], check=True)
            return True
        except Exception as e:
            print(f"❌ Não foi possível instalar o FFmpeg: {e}")
            return False

def get_direct_video_url(page_url):
    """Extrai a URL direta do stream de vídeo usando yt-dlp."""
    print(f"🕵️‍♂️ A extrair link real do vídeo: {page_url}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'socket_timeout': 30,
        'user_agent': HEADERS_PT['User-Agent'],
        'nocheckcertificate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
            video_url = info.get('url')
            if video_url:
                print("✅ Link direto obtido com sucesso!")
                return video_url
    except Exception as e:
        print(f"⚠️ Erro no yt-dlp: {e}")
    return None

def generate_snippet(video_direct_url, duration=3):
    """Gera um recorte de 3 segundos focado em conversão de vendas."""
    output_file = f"snippet_{int(time.time())}.mp4"
    print(f"✂️ A criar recorte de {duration} segundos...")
    
    # Comando FFmpeg otimizado para rapidez (ultrafast) e leveza
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-headers', f'User-Agent: {HEADERS_PT["User-Agent"]}\r\nReferer: https://www.xvideos.com/\r\n',
        '-ss', '00:00:12', # Pula o início para pegar uma cena de ação
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
            print(f"✅ Recorte pronto: {os.path.getsize(output_file) // 1024} KB")
            return output_file
    except Exception as e:
        print(f"⚠️ Falha no FFmpeg: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    return None

def send_to_telegram(data):
    """Envia o recorte para o Telegram com botões de pagamento."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    
    # Legenda limpa (Stealth): Sem links para o site original
    caption = f"🔞 <b>{data['titulo']}</b>\n\n"
    if CUSTOM_CAPTION:
        caption += f"💎 {CUSTOM_CAPTION}\n\n"
    else:
        caption += "🔥 <b>CONTEÚDO COMPLETO LIBERADO!</b>\n"
        caption += "✓ Acesso Vitalício (+5000 vídeos): R$ 19,99\n"
        caption += "✓ Vídeo Unitário: R$ 3,99\n\n"
    
    caption += "👇 <b>LIBERA O TEU ACESSO NO BOTÃO:</b>"

    # Botões direcionados apenas para o teu link de checkout
    reply_markup = {
        "inline_keyboard": [
            [{"text": "🔓 LIBERAR VÍDEO COMPLETO (PIX)", "url": BUTTON_LINK}],
            [{"text": "⭐ PACK COMPLETO VITALÍCIO", "url": BUTTON_LINK}]
        ]
    }

    print(f"🚀 A enviar vídeo monetizado para o grupo...")
    try:
        with open(data['path'], 'rb') as video_file:
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML',
                'supports_streaming': 'true',
                'reply_markup': json.dumps(reply_markup)
            }
            files = {'video': video_file}
            r = requests.post(api_url, data=payload, files=files, timeout=180)
            res = r.json()
            
        os.remove(data['path'])
        
        if res.get('ok'):
            print(f"✅ Sucesso: {data['titulo']}")
            return True
        else:
            print(f"❌ Erro Telegram: {res.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Erro no envio: {e}")
        return False

if __name__ == "__main__":
    # Diagnóstico de variáveis
    missing = []
    if not TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if not TARGET_URL: missing.append("TARGET_URL")
    if not BUTTON_LINK: missing.append("BUTTON_LINK")

    if missing:
        print(f"❌ ERRO CRÍTICO: Faltam as seguintes configurações: {', '.join(missing)}")
        sys.exit(1)

    if not check_ffmpeg():
        print("❌ Abortando: FFmpeg não disponível.")
        sys.exit(1)

    print("--- SNIPER ENGINE V3.5 INICIADA ---")
    
    links = []
    try:
        # Tenta ler listagem de vídeos (Scrapping em massa)
        response = scraper.get(TARGET_URL, headers=HEADERS_PT, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        
        for block in blocks:
            if len(links) >= 15: break # Limite aumentado para 15 vídeos
            try:
                a_tag = block.find('p', class_='title').find('a')
                links.append(f"https://www.xvideos.com{a_tag['href']}")
            except: continue
    except:
        # Se falhar a listagem, assume que é um vídeo único
        links = [TARGET_URL]

    if not links:
        print("❌ Nenhum vídeo encontrado para processar.")
        sys.exit(1)

    print(f"🎯 Total de itens para converter em lucro: {len(links)}")
    
    for url in links:
        try:
            # Captura o título em Português
            r = scraper.get(url, headers=HEADERS_PT, timeout=15)
            soup_vid = BeautifulSoup(r.text, 'html.parser')
            title = soup_vid.find("meta", property="og:title")["content"]
            title = title.replace(" - XVIDEOS.COM", "").strip()

            video_direct_url = get_direct_video_url(url)
            if video_direct_url:
                local_path = generate_snippet(video_direct_url, duration=3)
                if local_path:
                    send_to_telegram({"path": local_path, "titulo": title, "link": url})
                    time.sleep(15) # Intervalo anti-spam para o Telegram
        except Exception as e:
            print(f"⚠️ Falha ao processar item: {e}")
            continue

    print("--- OPERAÇÃO SNIPER FINALIZADA ---")
