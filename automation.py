import sys
import os
import json
import re
import requests
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class ScraperBase:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def fetch(self, url):
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.text

class XvideosScraper(ScraperBase):
    def scrape(self, url):
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.text.replace(" - XVIDEOS.COM", "").strip() if soup.title else "Sem título"
        video_url_match = re.search(r"html5player\.setVideoUrlHigh\('(.*?)'\);", html)
        if not video_url_match:
            video_url_match = re.search(r"html5player\.setVideoUrlLow\('(.*?)'\);", html)
        video_url = video_url_match.group(1) if video_url_match else None
        return {"plataforma": "Xvideos", "titulo": title, "arquivos": [video_url] if video_url else [], "link_original": url}

class EromeScraper(ScraperBase):
    def scrape(self, url):
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        if "/search?q=" in url:
            termo = url.split('q=')[-1].replace('+', ' ')
            title = f"Resultados da pesquisa: {termo}"
            album_links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/a/' in href and href not in album_links:
                    full_link = href if href.startswith('http') else f"https://www.erome.com{href}"
                    album_links.append(full_link)
            return {"plataforma": "Erome (Pesquisa)", "titulo": title, "arquivos": album_links, "link_original": url}
        else:
            title_tag = soup.find('h1')
            title = title_tag.text.strip() if title_tag else "Sem título"
            media_urls = []
            seen = set()
            for video_tag in soup.find_all('video'):
                source = video_tag.find('source')
                if source and source.get('src'):
                    src = source.get('src')
                    if src not in seen:
                        seen.add(src)
                        media_urls.append(src)
            return {"plataforma": "Erome (Álbum)", "titulo": title, "arquivos": media_urls, "link_original": url}

def processar_link(url):
    domain = urlparse(url).netloc.lower()
    try:
        if "xvideos.com" in domain: return XvideosScraper().scrape(url)
        elif "erome.com" in domain: return EromeScraper().scrape(url)
        else: return {"erro": "Domínio não suportado."}
    except Exception as e: return {"erro": str(e)}

if __name__ == "__main__":
    link_input = None
    dados_recebidos = {}
    config_data_env = os.environ.get('CONFIG_DATA')
    
    if config_data_env:
        try:
            dados_recebidos = json.loads(config_data_env)
            link_input = dados_recebidos.get('url_scraping', '').strip()
        except: pass

    if not link_input and len(sys.argv) > 1: link_input = sys.argv[1].strip()
    
    media_propria = dados_recebidos.get('media_propria', '').strip()
    qtd_solicitada = int(dados_recebidos.get('qtd', 1))
    puxar_titulo = dados_recebidos.get('puxar_titulo', True)
    copy_front = dados_recebidos.get('copy_principal', "").strip()
    has_spoiler = dados_recebidos.get('spoiler', False)
    bot_token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = dados_recebidos.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID")

    videos_para_baixar = []
    urls_rastreadas = set()
    
    if media_propria:
        videos_para_baixar.append((media_propria, "Conteúdo Exclusivo"))
    else:
        resultado = processar_link(link_input)
        if resultado.get("plataforma") == "Erome (Pesquisa)":
            for album_url in resultado.get("arquivos", []):
                if len(videos_para_baixar) >= qtd_solicitada: break
                res_album = processar_link(album_url)
                for v in res_album.get("arquivos", []):
                    if v not in urls_rastreadas:
                        urls_rastreadas.add(v)
                        videos_para_baixar.append((v, res_album.get("titulo", "Vídeo")))
                        if len(videos_para_baixar) >= qtd_solicitada: break
        else:
            for v in resultado.get("arquivos", []):
                if v not in urls_rastreadas:
                    urls_rastreadas.add(v)
                    videos_para_baixar.append((v, resultado.get("titulo", "Vídeo")))
                    if len(videos_para_baixar) >= qtd_solicitada: break

    api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    headers_dl = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.erome.com/"}

    for idx, (video_mp4, titulo_video) in enumerate(videos_para_baixar):
        legenda_partes = []
        if puxar_titulo in [True, "true"]: legenda_partes.append(f"🔥 {titulo_video}")
        if copy_front: legenda_partes.append(copy_front)
        legenda = "\n\n".join(legenda_partes) if legenda_partes else " "

        tmp_f = f"v_{idx}.mp4"
        tmp_c = f"c_{idx}.mp4"
        try:
            req = requests.get(video_mp4, headers=headers_dl, stream=True, timeout=60)
            with open(tmp_f, 'wb') as f:
                for chunk in req.iter_content(8192): f.write(chunk)
            
            cmd = ["ffmpeg", "-y", "-i", tmp_f, "-filter:v", "crop='trunc(iw/2)*2':'trunc((ih-150)/2)*2':0:0", "-preset", "ultrafast", "-c:a", "copy", tmp_c]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(tmp_c): os.remove(tmp_f); os.rename(tmp_c, tmp_f)
            
            with open(tmp_f, 'rb') as vf:
                requests.post(api_url, data={"chat_id": chat_id, "caption": legenda, "has_spoiler": str(has_spoiler).lower(), "parse_mode": "HTML"}, files={"video": vf}, timeout=300)
        finally:
            if os.path.exists(tmp_f): os.remove(tmp_f)
            if os.path.exists(tmp_c): os.remove(tmp_c)
