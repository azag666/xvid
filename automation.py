import os
import sys
import time
import requests
import json
import re
import subprocess

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS CRÍTICAS ---
try:
    import yt_dlp
except ImportError:
    print("⬇️ Instalando yt-dlp automaticamente...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
    import yt_dlp

try:
    import cloudscraper
except ImportError:
    print("⬇️ Instalando cloudscraper automaticamente...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper"])
    import cloudscraper

from bs4 import BeautifulSoup

# --- CONFIGURAÇÕES ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')
CUSTOM_CAPTION = os.environ.get('CUSTOM_CAPTION', '')

# Configura o scraper simulando um navegador
scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

# Cabeçalhos para FORÇAR o conteúdo em Português e simular tráfego real
HEADERS_PT = {
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def get_direct_video_url(page_url):
    """
    Usa yt-dlp de forma agressiva para extrair a URL direta do vídeo.
    """
    print(f"🕵️‍♂️ Extraindo link real do vídeo: {page_url}")
    
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
                print("✅ Link direto obtido via yt-dlp!")
                return video_url
    except Exception as e:
        print(f"⚠️ Erro no yt-dlp: {e}")
    
    # Plano B: Regex (Xvideos costuma expor isso em variáveis JS)
    print("🔄 Tentando extração via Regex...")
    try:
        response = scraper.get(page_url, headers=HEADERS_PT, timeout=20)
        html = response.text
        match = re.search(r"html5player\.setVideoUrlHigh\('([^']+)'\)", html)
        if not match:
            match = re.search(r"html5player\.setVideoUrlLow\('([^']+)'\)", html)
        
        if match:
            print("✅ Link extraído via Regex!")
            return match.group(1)
    except Exception as e:
        print(f"⚠️ Erro no Plano B: {e}")
        
    return None

def generate_snippet(video_direct_url, duration=30):
    """
    Gera um recorte do vídeo usando FFmpeg. 
    Aumentamos a velocidade e reduzimos o bitrate para garantir o envio.
    """
    output_file = f"video_{int(time.time())}.mp4"
    print(f"✂️ Criando recorte de {duration} segundos...")
    
    # Parâmetros otimizados para stream e velocidade
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-headers', f'User-Agent: {HEADERS_PT["User-Agent"]}\r\nReferer: https://www.xvideos.com/\r\n',
        '-ss', '00:00:05', # Pula os 5 primeiros segundos (geralmente intro)
        '-t', str(duration),
        '-i', video_direct_url,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32',
        '-c:a', 'aac', '-b:a', '64k',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_file
    ]
    
    try:
        # Timeout para evitar processos travados
        subprocess.run(cmd, check=True, timeout=300)
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 10000:
            print(f"✅ Recorte pronto: {os.path.getsize(output_file) // 1024} KB")
            return output_file
        else:
            print("❌ Arquivo gerado é inválido ou muito pequeno.")
    except Exception as e:
        print(f"⚠️ Falha no FFmpeg: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    
    return None

def process_single_video(url, custom_text=""):
    print(f"🔍 Analisando: {url}")
    try:
        # 1. Pegar título para a legenda
        response = scraper.get(url, headers=HEADERS_PT, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Vídeo"
        title = title.replace(" - XVIDEOS.COM", "").strip()

        # 2. Obter link direto e gerar recorte
        video_direct_url = get_direct_video_url(url)
        
        if video_direct_url:
            local_video_path = generate_snippet(video_direct_url)
            if local_video_path:
                return {
                    "type": "video",
                    "video_path": local_video_path,
                    "titulo": title,
                    "link": url,
                    "custom_text": custom_text
                }
        
        print(f"⏭️ Pulando {url} pois não foi possível gerar o vídeo.")
        return None
    except Exception as e:
        print(f"❌ Erro ao processar item: {e}")
        return None

def get_videos_from_listing(url):
    """Busca vídeos em listagens."""
    print(f"📑 Lendo lista em Português...")
    links = []
    try:
        response = scraper.get(url, headers=HEADERS_PT, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        
        count = 0
        for block in blocks:
            if count >= 5: break 
            try:
                a_tag = block.find('p', class_='title').find('a')
                full_link = f"https://www.xvideos.com{a_tag['href']}"
                links.append(full_link)
                count += 1
            except: continue
        return links
    except Exception as e:
        print(f"❌ Erro ao carregar listagem: {e}")
        return []

def send_video(data):
    """Envia o arquivo de vídeo recortado para o Telegram."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    
    caption = f"🇧🇷 <a href=\"{data['link']}\"><b>{data['titulo']}</b></a>"
    if data['custom_text']:
        caption += f"\n\n📣 {data['custom_text']}"

    print(f"🚀 Enviando vídeo para o grupo...")
    try:
        with open(data['video_path'], 'rb') as video_file:
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML',
                'supports_streaming': 'true'
            }
            files = {'video': video_file}
            r = requests.post(api_url, data=payload, files=files, timeout=300)
            res = r.json()
            
        # Limpeza
        os.remove(data['video_path'])
        
        if res.get('ok'):
            print("✅ Vídeo enviado com sucesso!")
            return True
        else:
            print(f"❌ Erro Telegram: {res.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Erro no envio: {e}")
        return False

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Configurações ausentes (TOKEN, ID ou URL).")
        sys.exit(1)

    # Identificar tipo de link
    urls_to_process = []
    if "/video" in TARGET_URL and "/channels/" not in TARGET_URL:
        urls_to_process.append(TARGET_URL)
    else:
        urls_to_process = get_videos_from_listing(TARGET_URL)

    if not urls_to_process:
        print("❌ Nenhum vídeo encontrado.")
        sys.exit(1)

    print(f"🎯 Iniciando processamento de {len(urls_to_process)} vídeo(s)...")
    
    success_count = 0
    for url in urls_to_process:
        video_data = process_single_video(url, CUSTOM_CAPTION)
        if video_data:
            if send_video(video_data):
                success_count += 1
            time.sleep(10) # Pausa entre envios
    
    if success_count == 0:
        print("❌ Nenhum vídeo foi enviado com sucesso.")
        sys.exit(1)
        
    print(f"🏁 Finalizado! {success_count} vídeo(s) enviado(s) ao grupo.")
