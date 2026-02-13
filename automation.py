import os
import sys
import cloudscraper
import time
import requests
import json
import re
import subprocess  # Necessário para rodar o comando de corte (ffmpeg)
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
    'Referer': 'https://www.google.com/'
}

def extract_mp4_url(html_content):
    """Tenta encontrar a URL do vídeo MP4"""
    try:
        mp4_match = re.search(r"html5player\.setVideoUrlHigh\('([^']+)'\)", html_content)
        if not mp4_match:
            mp4_match = re.search(r"html5player\.setVideoUrlLow\('([^']+)'\)", html_content)
        if mp4_match:
            return mp4_match.group(1)
    except:
        pass
    return None

def generate_snippet(video_url, duration=45):
    """
    Usa o FFmpeg para baixar e cortar os primeiros X segundos do vídeo.
    Retorna o caminho do arquivo local ou None se falhar.
    """
    output_file = f"snippet_{int(time.time())}.mp4"
    print(f"✂️ Gerando recorte de {duration} segundos...")
    
    # Comando FFmpeg otimizado para corte rápido e leve
    # -ss 0: começa do início
    # -t duration: duração do corte
    # -preset ultrafast: converte muito rápido para não gastar tempo do GitHub
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-i', video_url,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', # Re-encode leve
        '-c:a', 'aac', '-b:a', '64k',
        output_file
    ]
    
    try:
        # Executa o corte (timeout de 2 min para segurança)
        subprocess.run(cmd, check=True, timeout=120)
        
        # Verifica se o arquivo foi criado e tem tamanho válido
        if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
            print(f"✅ Recorte gerado: {output_file}")
            return output_file
    except Exception as e:
        print(f"⚠️ Falha ao gerar recorte: {e}")
        if os.path.exists(output_file): os.remove(output_file)
    
    return None

def process_single_video(url, custom_text=""):
    print(f"🔄 Processando: {url}")
    try:
        # Adiciona headers=HEADERS_PT para pegar título em Português
        response = scraper.get(url, headers=HEADERS_PT, timeout=25)
        if response.status_code != 200: 
            print(f"❌ Erro HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Título
        og_title = soup.find("meta", property="og:title")
        title = og_title["content"] if og_title else "Vídeo Hot"
        title = title.replace(" - XVIDEOS.COM", "").replace("XVIDEOS.COM - ", "").strip()

        # Thumbnail
        og_image = soup.find("meta", property="og:image")
        thumbnail = og_image["content"] if og_image else None
        
        # Vídeo MP4
        mp4_url = extract_mp4_url(response.text)
        
        # Se achou MP4, tenta gerar o recorte físico
        local_video_path = None
        if mp4_url:
            local_video_path = generate_snippet(mp4_url)

        return {
            "type": "video" if local_video_path else "photo",
            "video_path": local_video_path, # Caminho do arquivo no disco
            "photo_url": thumbnail,
            "titulo": title,
            "link": url,
            "custom_text": custom_text
        }
    except Exception as e:
        print(f"❌ Erro scraper: {e}")
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
        print(f"❌ Erro lista: {e}")
        return []

def send_payload(method, payload, files=None):
    """Função auxiliar para envio"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        # Se tiver arquivos (video), usa multipart upload
        if files:
            r = requests.post(url, data=payload, files=files, timeout=120)
        else:
            r = requests.post(url, data=payload, timeout=60)
        return r.json()
    except Exception as e:
        return {'ok': False, 'description': str(e)}

def smart_send(data):
    """Envia recorte de vídeo ou foto"""
    
    # Legenda com Título em Português
    caption = f"🇧🇷 <a href=\"{data['link']}\"><b>{data['titulo']}</b></a>"
    if data['custom_text']:
        caption += f"\n\n📣 {data['custom_text']}"

    # TENTATIVA 1: Enviar Recorte de Vídeo (Arquivo Local)
    if data['type'] == 'video' and data['video_path']:
        print("🎥 Enviando recorte MP4 para o Telegram...")
        try:
            with open(data['video_path'], 'rb') as video_file:
                res = send_payload('sendVideo', {
                    'chat_id': CHAT_ID,
                    'caption': caption,
                    'parse_mode': 'HTML',
                    'supports_streaming': 'true'
                }, files={'video': video_file})
            
            # Limpa o arquivo depois de tentar enviar
            os.remove(data['video_path'])
            
            if res.get('ok'):
                print("✅ Recorte enviado com sucesso!")
                return True
            else:
                print(f"⚠️ Falha ao enviar vídeo: {res.get('description')}")
        except Exception as e:
            print(f"⚠️ Erro ao ler arquivo de vídeo: {e}")

    # TENTATIVA 2: Enviar Foto (Fallback)
    if data['photo_url']:
        print("🔄 Fallback: Enviando Thumbnail...")
        res = send_payload('sendPhoto', {
            'chat_id': CHAT_ID,
            'photo': data['photo_url'],
            'caption': caption,
            'parse_mode': 'HTML'
        })
        
        if res.get('ok'):
            print("✅ Foto enviada com sucesso!")
            return True
            
    return False

if __name__ == "__main__":
    if not all([TELEGRAM_TOKEN, CHAT_ID, TARGET_URL]):
        print("❌ Configurações faltando.")
        sys.exit(1)

    urls_to_process = []
    if "/video" in TARGET_URL and "/channels/" not in TARGET_URL:
        urls_to_process.append(TARGET_URL)
    else:
        urls_to_process = get_videos_from_listing(TARGET_URL)

    if not urls_to_process:
        print("❌ Nenhum link encontrado.")
        sys.exit(1)

    print(f"🎯 Processando {len(urls_to_process)} itens...")
    
    success_count = 0
    for url in urls_to_process:
        data = process_single_video(url, CUSTOM_CAPTION)
        if data:
            if smart_send(data):
                success_count += 1
            time.sleep(5)
    
    if success_count == 0:
        print("❌ Todos os envios falharam.")
        sys.exit(1)
        
    print(f"🏁 Finalizado. {success_count}/{len(urls_to_process)} enviados.")
