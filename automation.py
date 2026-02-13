import os
import sys
import time
import requests
import json
import re
import subprocess

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS CRÍTICAS ---
# Garante que temos o yt-dlp (melhor extrator de vídeos do mundo)
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

# Cabeçalhos para FORÇAR o conteúdo em Português
HEADERS_PT = {
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def get_direct_video_url(page_url):
    """
    Usa yt-dlp para extrair a URL direta do vídeo.
    Adicionamos headers extras para evitar bloqueios.
    """
    print("🕵️‍♂️ Extraindo link real do vídeo com yt-dlp...")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'socket_timeout': 15,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
            video_url = info.get('url')
            if video_url:
                print("✅ Link direto do vídeo obtido!")
                return video_url
    except Exception as e:
        print(f"⚠️ Erro no yt-dlp: {e}")
    
    # Plano B: Tentar extrair via Regex se o yt-dlp falhar
    print("🔄 Tentando Plano B (Regex)...")
    try:
        response = scraper.get(page_url, headers=HEADERS_PT, timeout=20)
        html = response.text
        # Procura por links de alta ou baixa qualidade no JS da página
        match = re.search(r"html5player\.setVideoUrlHigh\('([^']+)'\)", html)
        if not match:
            match = re.search(r"html5player\.setVideoUrlLow\('([^']+)'\)", html)
        
        if match:
            print("✅ Link extraído via Regex!")
            return match.group(1)
    except Exception as e:
        print(f"⚠️ Erro no Plano B: {e}")
        
    return None

def generate_snippet(video_direct_url, duration=45):
    """
    Usa o FFmpeg para criar um recorte leve dos primeiros segundos.
    Otimizado para ser rápido.
    """
    output_file = f"snippet_{int(time.time())}.mp4"
    print(f"✂️ Gerando recorte de {duration} segundos...")
    
    # Comando FFmpeg otimizado
    # -t duration ANTES de -i faz o ffmpeg ler apenas o necessário do stream
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-headers', f'User-Agent: {HEADERS_PT["User-Agent"]}\r\nReferer: https://www.xvideos.com/\r\n',
        '-t', str(duration),
        '-i', video_direct_url,
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30',
        '-c:a', 'aac', '-b:a', '64k',
        '-movflags', '+faststart',
        output_file
    ]
    
    try:
        # Timeout de 4 minutos para o download/corte
        subprocess.run(cmd, check=True, timeout=240)
        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 5000:
            print(f"✅ Recorte gerado: {os.path.getsize(output_file) // 1024} KB")
            return output_file
    except Exception as e:
        print(f"⚠️ Falha no FFmpeg: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    
    return None

def process_single_video(url, custom_text=""):
    print(f"🔄 Processando página: {url}")
    try:
        # 1. Pega metadados básicos
        response = scraper.get(url, headers=HEADERS_PT, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Vídeo Hot"
        title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()

        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None
        
        # 2. Pega URL real do Vídeo
        video_direct_url = get_direct_video_url(url)
        
        # 3. Gera o recorte se conseguiu o link
        local_video_path = None
        if video_direct_url:
            local_video_path = generate_snippet(video_direct_url)
        else:
            print("❌ Não foi possível extrair o link do vídeo.")

        return {
            "type": "video" if local_video_path else "photo",
            "video_path": local_video_path,
            "photo_url": thumbnail,
            "titulo": title,
            "link": url,
            "custom_text": custom_text
        }
    except Exception as e:
        print(f"❌ Erro geral ao processar: {e}")
        return None

def get_videos_from_listing(url):
    """Busca vídeos em páginas de categoria"""
    print(f"📑 Lendo lista de vídeos (PT-BR)...")
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
        print(f"❌ Erro ao ler listagem: {e}")
        return []

def send_payload(method, payload, files=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if files:
            r = requests.post(url, data=payload, files=files, timeout=180)
        else:
            r = requests.post(url, data=payload, timeout=60)
        return r.json()
    except Exception as e:
        return {'ok': False, 'description': str(e)}

def smart_send(data):
    # Legenda Clean com Título linkado
    caption = f"🇧🇷 <a href=\"{data['link']}\"><b>{data['titulo']}</b></a>"
    if data['custom_text']:
        caption += f"\n\n📣 {data['custom_text']}"

    # Prioridade 1: Enviar Recorte de Vídeo
    if data['type'] == 'video' and data['video_path']:
        print("🎥 Enviando vídeo para o Telegram...")
        try:
            with open(data['video_path'], 'rb') as video_file:
                res = send_payload('sendVideo', {
                    'chat_id': CHAT_ID,
                    'caption': caption,
                    'parse_mode': 'HTML',
                    'supports_streaming': 'true'
                }, files={'video': video_file})
            
            os.remove(data['video_path'])
            
            if res.get('ok'):
                print("✅ Vídeo enviado com sucesso!")
                return True
            else:
                print(f"⚠️ Erro Telegram (Vídeo): {res.get('description')}")
                print("🔄 Tentando Fallback para Foto...")
        except Exception as e:
            print(f"⚠️ Erro ao manipular arquivo de vídeo: {e}")

    # Prioridade 2: Enviar Foto (Fallback ou se não houver vídeo)
    if data['photo_url']:
        print("📸 Enviando Foto...")
        res = send_payload('sendPhoto', {
            'chat_id': CHAT_ID,
            'photo': data['photo_url'],
            'caption': caption,
            'parse_mode': 'HTML'
        })
        
        if res.get('ok'):
            print("✅ Foto enviada com sucesso!")
            return True
        else:
            print(f"❌ Falha no Telegram (Foto): {res.get('description')}")
            
    return False

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Configurações faltando (TOKEN, ID ou URL).")
        sys.exit(1)

    urls_to_process = []
    if "/video" in TARGET_URL and "/channels/" not in TARGET_URL:
        urls_to_process.append(TARGET_URL)
    else:
        urls_to_process = get_videos_from_listing(TARGET_URL)

    if not urls_to_process:
        print("❌ Nenhum vídeo encontrado no link fornecido.")
        sys.exit(1)

    print(f"🎯 Iniciando processamento de {len(urls_to_process)} vídeo(s)...")
    
    success_count = 0
    for url in urls_to_process:
        data = process_single_video(url, CUSTOM_CAPTION)
        if data:
            if smart_send(data):
                success_count += 1
            # Pausa para evitar bloqueio do Telegram
            time.sleep(7)
    
    if success_count == 0:
        print("❌ Nenhum envio foi concluído com sucesso.")
        sys.exit(1)
        
    print(f"🏁 Finalizado! Sucessos: {success_count}/{len(urls_to_process)}")
