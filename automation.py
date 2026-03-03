import os
import sys
import time
import requests
import json
import subprocess
import functools

# FORÇA O PYTHON A MOSTRAR OS LOGS NO GITHUB EM TEMPO REAL
print = functools.partial(print, flush=True)

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS CRÍTICAS ---
def install_package(package):
    try:
        print(f"⬇️ A instalar {package} automaticamente...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except Exception as e:
        print(f"❌ Erro ao instalar {package}: {e}")

# Garante que o yt-dlp e cloudscraper estão presentes
try:
    import yt_dlp
except ImportError:
    install_package("yt-dlp")
    import yt_dlp

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

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

HEADERS_PT = {
    'Accept-Language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.google.com/'
}

def check_ffmpeg():
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
    print(f"🕵️‍♂️ A extrair link real: {page_url}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'socket_timeout': 15,
        'user_agent': HEADERS_PT['User-Agent'],
        'nocheckcertificate': True,
        'noplaylist': True
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

def generate_snippet(video_direct_url, duration=20):
    output_file = f"snippet_{int(time.time())}.mp4"
    print(f"✂️ A criar recorte de {duration} segundos...")
    
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
        '-headers', f'User-Agent: {HEADERS_PT["User-Agent"]}\r\nReferer: https://www.xvideos.com/\r\n',
        '-ss', '00:00:12', 
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
    except subprocess.TimeoutExpired:
        print("⚠️ O vídeo demorou demasiado a processar. A saltar para o próximo.")
        if os.path.exists(output_file): os.remove(output_file)
    except Exception as e:
        print(f"⚠️ Falha no FFmpeg: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    return None

def send_to_telegram(data):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    caption = f"🔞 <b>{data['titulo']}</b>"

    print(f"🚀 A enviar '{data['titulo']}' para o grupo...")
    try:
        with open(data['path'], 'rb') as video_file:
            # AQUI ESTAVA O ERRO: REMOVI COMPLETAMENTE O "reply_markup" QUE CRIAVA BOTÕES INVÁLIDOS
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML',
                'supports_streaming': 'true'
            }
            files = {'video': video_file}
            r = requests.post(api_url, data=payload, files=files, timeout=60)
            res = r.json()
            
        os.remove(data['path'])
        
        if res.get('ok'):
            print(f"✅ Sucesso no envio do vídeo!")
            return True
        else:
            print(f"❌ Erro Telegram: {res.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Erro no envio da rede: {e}")
        return False

if __name__ == "__main__":
    missing = []
    if not TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID: missing.append("TELEGRAM_CHAT_ID")
    if not TARGET_URL: missing.append("TARGET_URL")

    if missing:
        print(f"❌ ERRO CRÍTICO: Faltam as seguintes configurações: {', '.join(missing)}")
        sys.exit(1)

    if not check_ffmpeg():
        print("❌ Abortando: FFmpeg não disponível.")
        sys.exit(1)

    print(f"--- SNIPER ENGINE EXTRAÇÃO INICIADA ---")
    print(f"🔗 Alvo: {TARGET_URL}")
    
    links = []
    try:
        response = scraper.get(TARGET_URL, headers=HEADERS_PT, timeout=25)
        soup = BeautifulSoup(response.text, 'html.parser')
        blocks = soup.find_all('div', class_='thumb-block')
        
        for block in blocks:
            if len(links) >= 20: break
            try:
                a_tag = block.find('p', class_='title').find('a')
                links.append(f"https://www.xvideos.com{a_tag['href']}")
            except: continue
            
        print(f"🕵️ Encontrados {len(links)} vídeos na página de listagem.")
    except Exception as e:
        print(f"⚠️ Erro ao procurar vídeos na página: {e}")

    if not links:
        print("⚠️ A tentar tratar o link fornecido como um vídeo único.")
        links = [TARGET_URL]

    print(f"🎯 Total a processar agora: {len(links)}")
    
    for idx, url in enumerate(links, start=1):
        print(f"\n--- A Processar Vídeo {idx}/{len(links)} ---")
        try:
            r = scraper.get(url, headers=HEADERS_PT, timeout=15)
            soup_vid = BeautifulSoup(r.text, 'html.parser')
            
            try:
                title = soup_vid.find("meta", property="og:title")["content"]
                title = title.replace(" - XVIDEOS.COM", "").strip()
            except:
                title = "Conteúdo Exclusivo"

            video_direct_url = get_direct_video_url(url)
            if video_direct_url:
                local_path = generate_snippet(video_direct_url, duration=20)
                if local_path:
                    sucesso = send_to_telegram({"path": local_path, "titulo": title})
                    if sucesso:
                        print("⏳ A aguardar 5 segundos para não spammar o Telegram...")
                        time.sleep(5) 
        except Exception as e:
            print(f"⚠️ Falha fatal ao processar item {idx}: {e}")
            continue

    print("\n--- ✅ OPERAÇÃO SNIPER FINALIZADA ✅ ---")
