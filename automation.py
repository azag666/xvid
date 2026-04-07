import os
import sys
import time
import requests
import json
import subprocess
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

# Configurações do GitHub Actions
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TARGET_URL = os.environ.get('TARGET_URL')

# SEU CHECKOUT DE ALTA CONVERSÃO
MEU_CHECKOUT = "https://telegramvipp.netlify.app/" 

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

def traduzir_para_pt(texto):
    """
    Usa a API pública do Google Translate para converter qualquer idioma para Português (PT)
    """
    try:
        texto_seguro = urllib.parse.quote(texto)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=pt&dt=t&q={texto_seguro}"
        resposta = requests.get(url, timeout=5)
        # O Google devolve um JSON complexo, a tradução fica no primeiro índice
        texto_traduzido = resposta.json()[0][0][0]
        return texto_traduzido
    except Exception as e:
        print(f"⚠️ Aviso (Tradução falhou, a usar original): {e}", flush=True)
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

def generate_snippet(video_direct_url):
    output_file = f"video_{int(time.time())}.mp4"
    print("✂️ Criando teaser rápido...", flush=True)
    cmd = [
        'ffmpeg', '-y', '-ss', '00:00:05', '-t', '20', 
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

def send_to_telegram(path, titulo_pt):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    
    caption = (
        f"🔞 <b>{titulo_pt}</b>\n\n"
        f"🔥 <b>ACESSO VITALÍCIO LIBERADO!</b>\n\n"
        f"✅ <i>Sem cortes ou censura</i>\n"
        f"✅ <i>+100 vídeos novos por dia</i>\n"
        f"✅ <i>Acesso a TODOS os vídeos do canal</i>\n\n"
        f"👇 <b>CLIQUE NO BOTÃO VERDE ABAIXO POR APENAS R$ 9,99</b> 👇"
    )
    
    # Encurta o título para não estragar o design do botão no telemóvel
    titulo_curto = titulo_pt[:20] + "..." if len(titulo_pt) > 20 else titulo_pt
    
    reply_markup = {
        "inline_keyboard": [
            [{"text": f"🟩 ASSISTIR: {titulo_curto} (R$ 9,99) ✅", "url": MEU_CHECKOUT}]
        ]
    }
    
    payload = {
        'chat_id': CHAT_ID,
        'caption': caption,
        'parse_mode': 'HTML',
        'supports_streaming': 'true',
        'reply_markup': json.dumps(reply_markup)
    }
    
    try:
        with open(path, 'rb') as f:
            r = requests.post(api_url, data=payload, files={'video': f}, timeout=60)
            if not r.json().get('ok'):
                print(f"❌ Erro do Telegram: {r.text}", flush=True)
            return r.json().get('ok')
    except Exception as e:
        print(f"❌ Erro no envio: {e}", flush=True)
        return False

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID or not TARGET_URL:
        print("❌ ERRO: Faltam configurações no GitHub", flush=True)
        sys.exit(1)

    print(f"🚀 Sniper Engine Iniciada - Alvo: {TARGET_URL}", flush=True)
    
    links = []
    if "/video." in TARGET_URL:
        links = [TARGET_URL]
    else:
        try:
            res = scraper.get(TARGET_URL, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.select('p.title a'):
                if len(links) >= 20: break  # GARANTIA DE 20 VÍDEOS MÁXIMO
                links.append(f"https://www.xvideos.com{a['href']}")
        except Exception as e:
            print(f"❌ Erro no Scraping: {e}", flush=True)

    print(f"🎯 Total na fila para este disparo: {len(links)} vídeos", flush=True)

    contador = 0
    for url in links:
        video_direct = get_direct_video_url(url)
        if video_direct:
            path = generate_snippet(video_direct)
            if path:
                # 1. Tenta raspar o título real da página
                try:
                    res_title = scraper.get(url, timeout=10)
                    soup_title = BeautifulSoup(res_title.text, 'html.parser')
                    title_original = soup_title.find("meta", property="og:title")["content"].replace(" - XVIDEOS.COM", "").strip()
                except:
                    title_original = "Conteúdo Exclusivo Premium"

                # 2. TRADUZ O TÍTULO PARA PORTUGUÊS
                title_pt = traduzir_para_pt(title_original)

                # 3. Envia para o Telegram com o título em PT
                if send_to_telegram(path, title_pt):
                    contador += 1
                    print(f"✅ [{contador}/{len(links)}] Postado (Traduzido): {title_pt}", flush=True)
                    time.sleep(3) # Pausa curta
                
                if os.path.exists(path): os.remove(path)
                
    print(f"🏁 Finalizado! {contador} vídeos enviados para o grupo.", flush=True)
