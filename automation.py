import sys
import os
import json
import re
import requests
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
            # Lê exatamente a chave do novo Frontend
            link_input = dados_recebidos.get('url_scraping')
            
            # Lê outras configurações opcionais do painel
            chat_id = dados_recebidos.get('chat_id')
            puxar_titulo = dados_recebidos.get('puxar_titulo')
            
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
    
    # 4. EXECUTA O SCRAPING
    resultado = processar_link(link_input)
    
    print("\n" + "="*30)
    print("      RESULTADO DA EXTRAÇÃO")
    print("="*30)
    
    if "erro" in resultado:
        print(f"❌ {resultado['erro']}")
        sys.exit(1)
        
    for chave, valor in resultado.items():
        if isinstance(valor, list):
            print(f"{chave.upper()}:")
            if not valor:
                print("  -> Nenhum arquivo encontrado.")
            for item in valor:
                print(f"  -> {item}")
        else:
            print(f"{chave.upper()}: {valor}")
            
    print("="*30)
    print("[✓] Processo concluído com sucesso.")
    # A partir daqui, seu código original do vendedor.py assume para disparar pro Telegram!
