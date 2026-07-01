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
        
        # Modo Pesquisa
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
            
        # Modo Álbum/Vídeo
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

    # 1. TENTA LER O PAYLOAD DO FRONTEND
    config_data_env = os.environ.get('CONFIG_DATA')
    
    if config_data_env:
        try:
            dados_recebidos = json.loads(config_data_env)
            link_input = dados_recebidos.get('url_scraping')
            print("[*] Comando JSON recebido com sucesso do Front-end Sniper Control!")
        except json.JSONDecodeError:
            print("[!] Erro crítico: O Front-end enviou um payload inválido.")

    # 2. SE NÃO VEIO DO FRONT, TENTA MODO MANUAL (Via terminal)
    if not link_input and len(sys.argv) > 1:
        link_input = sys.argv[1].strip()
        print("[*] Comando manual recebido via argumento.")

    # 3. VALIDAÇÃO FINAL
    if not link_input:
        print("[!] Nenhum link fornecido ('url_scraping' vazia). Encerrando o robô.")
        sys.exit(1)

    print(f"\n[*] Iniciando extração para a URL: {link_input}")
    
    # 4. EXECUTA O SCRAPING INICIAL
    resultado = processar_link(link_input)
    
    print("\n" + "="*30)
    print("      RESULTADO DA EXTRAÇÃO")
    print("="*30)
    
    if "erro" in resultado:
        print(f"❌ {resultado['erro']}")
        sys.exit(1)
        
    # --- 5. LÓGICA DE NAVEGAÇÃO DE PESQUISA ---
    if resultado.get("plataforma") == "Erome (Pesquisa)" and resultado.get("arquivos"):
        primeiro_album = resultado["arquivos"][0]
        print(f"\n[*] Pesquisa detectada. Entrando no 1º álbum: {primeiro_album}")
        
        resultado = processar_link(primeiro_album)
        
        if "erro" in resultado:
            print(f"❌ Erro ao ler o álbum: {resultado['erro']}")
            sys.exit(1)

    # --- 6. PREPARAÇÃO DO VÍDEO ---
    arquivos_encontrados = resultado.get("arquivos", [])
    if not arquivos_encontrados:
        print("  -> Nenhum vídeo mp4 encontrado na página.")
        sys.exit(1)
        
    video_mp4 = arquivos_encontrados[0]
    titulo_video = resultado.get("titulo", "Vídeo")
    
    print(f"[*] Vídeo alvo extraído com sucesso: {video_mp4}")
    
    # --- 7. DISPARO PARA O TELEGRAM (COM DOWNLOAD, CORTE E UPLOAD) ---
    bot_token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = dados_recebidos.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[!] ERRO: TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausentes.")
        sys.exit(1)

    print(f"\n[*] Preparando disparo para o Telegram... (Chat ID: {chat_id})")

    copy_front = dados_recebidos.get("copy_principal", "")
    legenda = f"🔥 {titulo_video}\n\n{copy_front}" if copy_front else f"🔥 {titulo_video}"

    api_url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    temp_filename = "video_temp.mp4"
    temp_cropped = "video_temp_cropped.mp4"

    try:
        print("[*] Baixando o vídeo...")
        headers_download = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.erome.com/"
        }
        
        vid_resposta = requests.get(video_mp4, headers=headers_download, stream=True, timeout=60)
        vid_resposta.raise_for_status()
        
        with open(temp_filename, 'wb') as f:
            for chunk in vid_resposta.iter_content(chunk_size=8192):
                f.write(chunk)
                
        # --- ETAPA DE CORTE DA MARCA D'ÁGUA (FFMPEG) ---
        print("[*] Aplicando corte para remover marca d'água inferior (FFmpeg)...")
        # 'crop=iw:ih-90:0:0' -> Mantém a largura (iw), tira 90 pixels da altura (ih-90), começando do topo (0,0)
        comando_ffmpeg = [
            "ffmpeg", "-y", "-i", temp_filename,
            "-filter:v", "crop=iw:ih-90:0:0",
            "-preset", "ultrafast",
            "-c:a", "copy",
            temp_cropped
        ]
        
        try:
            # Executa o FFmpeg ocultando os logs visuais para não poluir o terminal
            subprocess.run(comando_ffmpeg, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Se o corte deu certo, substitui o arquivo original pelo cortado
            if os.path.exists(temp_cropped):
                os.remove(temp_filename)
                os.rename(temp_cropped, temp_filename)
                print("[*] Corte da marca d'água concluído com sucesso!")
        except Exception as e:
            print(f"[!] Erro ao tentar cortar o vídeo. Enviando versão original por segurança: {e}")

        # --- UPLOAD PARA O TELEGRAM ---
        print("[*] Fazendo upload para o Telegram...")
        
        with open(temp_filename, 'rb') as video_file:
            payload = {"chat_id": chat_id, "caption": legenda}
            files = {"video": video_file}
            
            req = requests.post(api_url, data=payload, files=files, timeout=300)
            resp = req.json()
        
        # Limpeza dos arquivos temporários
        if os.path.exists(temp_filename): os.remove(temp_filename)
        if os.path.exists(temp_cropped): os.remove(temp_cropped)
        
        if resp.get("ok"):
            print("[✓] SUCESSO ABSOLUTO! Vídeo publicado no seu canal do Telegram sem a marca inferior.")
        else:
            print(f"[!] Erro retornado pelo Telegram: {resp.get('description')}")
            
    except Exception as e:
        print(f"[!] Erro crítico de conexão ao processar ou disparar o vídeo: {str(e)}")
        if os.path.exists(temp_filename): os.remove(temp_filename)
        if os.path.exists(temp_cropped): os.remove(temp_cropped)
