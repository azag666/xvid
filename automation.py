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
            for video_tag in soup.find_all('video'):
                source = video_tag.find('source')
                if source and source.get('src'):
                    media_urls.append(source.get('src'))
            return {"plataforma": "Erome (Álbum)", "titulo": title, "arquivos": media_urls, "link_original": url}

def processar_link(url):
    domain = urlparse(url).netloc.lower()
    try:
        if "xvideos.com" in domain:
            return XvideosScraper().scrape(url)
        elif "erome.com" in domain:
            return EromeScraper().scrape(url)
        else:
            return {"erro": "Domínio não suportado. Insira um link do Xvideos ou Erome."}
    except Exception as e:
        return {"erro": f"Erro: {str(e)}"}

if __name__ == "__main__":
    link_input = None
    dados_recebidos = {}

    # --- 1. LÊ DADOS DO FRONTEND ---
    config_data_env = os.environ.get('CONFIG_DATA')
    if config_data_env:
        try:
            dados_recebidos = json.loads(config_data_env)
            link_input = dados_recebidos.get('url_scraping', '').strip()
            print("[*] Payload do Frontend lido com sucesso!")
        except json.JSONDecodeError:
            print("[!] Erro crítico: O Front-end enviou um payload inválido.")

    if not link_input and not dados_recebidos.get('media_propria') and len(sys.argv) > 1:
        link_input = sys.argv[1].strip()

    media_propria = dados_recebidos.get('media_propria', '').strip()
    
    if not link_input and not media_propria:
        print("[!] Nenhum link ou mídia própria fornecida. Encerrando.")
        sys.exit(1)

    # Variáveis de configuração do Front-end
    qtd_solicitada = int(dados_recebidos.get('qtd', 1))
    puxar_titulo = dados_recebidos.get('puxar_titulo', True)
    copy_front = dados_recebidos.get('copy_principal', "").strip()
    has_spoiler = dados_recebidos.get('spoiler', False)
    
    bot_token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = dados_recebidos.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[!] ERRO: TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausentes no GitHub.")
        sys.exit(1)

    # --- 2. COLETA OS VÍDEOS COM BASE NA QUANTIDADE ---
    videos_para_baixar = []
    
    if media_propria:
        videos_para_baixar.append((media_propria, "Conteúdo Exclusivo"))
        print(f"[*] Mídia Própria detectada. Pulando scraping.")
    else:
        print(f"\n[*] Extraindo vídeos de: {link_input}")
        resultado = processar_link(link_input)
        if "erro" in resultado:
            print(f"❌ {resultado['erro']}")
            sys.exit(1)
            
        if resultado.get("plataforma") == "Erome (Pesquisa)" and resultado.get("arquivos"):
            for album_url in resultado["arquivos"]:
                if len(videos_para_baixar) >= qtd_solicitada:
                    break
                print(f"[*] Acessando álbum: {album_url}")
                res_album = processar_link(album_url)
                if "erro" not in res_album and res_album.get("arquivos"):
                    for v in res_album["arquivos"]:
                        if len(videos_para_baixar) >= qtd_solicitada:
                            break
                        videos_para_baixar.append((v, res_album.get("titulo", "Vídeo")))
        else:
            for v in resultado.get("arquivos", []):
                if len(videos_para_baixar) >= qtd_solicitada:
                    break
                videos_para_baixar.append((v, resultado.get("titulo", "Vídeo")))

    if not videos_para_baixar:
        print("❌ Nenhum vídeo encontrado para download.")
        sys.exit(1)

    print(f"\n[*] Total de {len(videos_para_baixar)} vídeo(s) para processar.")

    api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    headers_download = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0)", "Referer": "https://www.erome.com/"}

    # --- 3. LOOP DE DOWNLOAD, CORTE E ENVIO (RESPEITANDO 'QTD') ---
    for idx, (video_mp4, titulo_video) in enumerate(videos_para_baixar):
        print(f"\n--- [Processando Vídeo {idx+1}/{len(videos_para_baixar)}] ---")
        
        # Constrói a legenda exatamente como configurado no front
        partes_legenda = []
        if puxar_titulo:
            partes_legenda.append(f"🔥 {titulo_video}")
        if copy_front:
            partes_legenda.append(copy_front)
            
        legenda = "\n\n".join(partes_legenda)

        temp_filename = f"video_temp_{idx}.mp4"
        temp_cropped = f"video_temp_cropped_{idx}.mp4"

        try:
            # DOWNLOAD
            print("[*] Baixando arquivo fonte...")
            vid_resposta = requests.get(video_mp4, headers=headers_download, stream=True, timeout=60)
            vid_resposta.raise_for_status()
            
            with open(temp_filename, 'wb') as f:
                for chunk in vid_resposta.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # CORTE FFMPEG (Aumentado para 140 pixels)
            print("[*] Aplicando corte para remover marca d'água inferior (ih-140)...")
            comando_ffmpeg = [
                "ffmpeg", "-y", "-i", temp_filename,
                "-filter:v", "crop=iw:ih-140:0:0", 
                "-preset", "ultrafast",
                "-c:a", "copy",
                temp_cropped
            ]
            
            subprocess.run(comando_ffmpeg, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if os.path.exists(temp_cropped):
                os.remove(temp_filename)
                os.rename(temp_cropped, temp_filename)
            
            # UPLOAD TELEGRAM
            print("[*] Fazendo upload para o canal...")
            with open(temp_filename, 'rb') as video_file:
                payload = {
                    "chat_id": chat_id, 
                    "caption": legenda,
                    "has_spoiler": str(has_spoiler).lower(),
                    "parse_mode": "HTML"
                }
                files = {"video": video_file}
                req = requests.post(api_url, data=payload, files=files, timeout=300)
                resp = req.json()
            
            if resp.get("ok"):
                print(f"[✓] Vídeo {idx+1} publicado com sucesso!")
            else:
                print(f"[!] Erro no vídeo {idx+1}: {resp.get('description')}")
                
        except Exception as e:
            print(f"[!] Erro no vídeo {idx+1}: {str(e)}")
            
        finally:
            if os.path.exists(temp_filename): os.remove(temp_filename)
            if os.path.exists(temp_cropped): os.remove(temp_cropped)

    print("\n[✓] Fila de envios concluída.")
