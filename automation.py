import sys
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

class ScraperBase:
    def __init__(self):
        # User-Agent atualizado para evitar bloqueios simples
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def fetch(self, url):
        """Faz a requisição HTTP e retorna o HTML."""
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.text

class XvideosScraper(ScraperBase):
    def scrape(self, url):
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extrai o título da página
        title = soup.title.text if soup.title else "Sem título"
        title = title.replace(" - XVIDEOS.COM", "").strip()
        
        # O Xvideos geralmente armazena a URL do vídeo mp4 no próprio HTML via JavaScript
        video_url_match = re.search(r"html5player\.setVideoUrlHigh\('(.*?)'\);", html)
        
        # Fallback para qualidade baixa se a alta não existir
        if not video_url_match:
            video_url_match = re.search(r"html5player\.setVideoUrlLow\('(.*?)'\);", html)
            
        video_url = video_url_match.group(1) if video_url_match else None
        
        return {
            "plataforma": "Xvideos",
            "titulo": title,
            "arquivos": [video_url] if video_url else [],
            "link_original": url
        }

class EromeScraper(ScraperBase):
    def scrape(self, url):
        html = self.fetch(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. CENÁRIO: Página de Pesquisa
        if "/search?q=" in url:
            # Pega o termo pesquisado da URL
            termo = url.split('q=')[-1].replace('+', ' ')
            title = f"Resultados da pesquisa: {termo}"
            
            album_links = []
            # Procura por todas as tags <a> que contêm '/a/' (links de álbuns)
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/a/' in href and href not in album_links:
                    # Garante que o link esteja completo
                    full_link = href if href.startswith('http') else f"https://www.erome.com{href}"
                    album_links.append(full_link)
            
            return {
                "plataforma": "Erome (Pesquisa)",
                "titulo": title,
                "arquivos": album_links, # Retorna a lista de links para os álbuns
                "link_original": url
            }
            
        # 2. CENÁRIO: Página de Álbum/Vídeo Específico
        else:
            title_tag = soup.find('h1')
            title = title_tag.text.strip() if title_tag else "Sem título"
            
            media_urls = []
            # Extrai os vídeos da página
            for video_tag in soup.find_all('video'):
                source = video_tag.find('source')
                if source and source.get('src'):
                    media_urls.append(source.get('src'))
                    
            return {
                "plataforma": "Erome (Álbum)",
                "titulo": title,
                "arquivos": media_urls, # Retorna os links diretos dos vídeos
                "link_original": url
            }

def processar_link(url):
    """Identifica o domínio e direciona para o scraper correto."""
    domain = urlparse(url).netloc.lower()
    
    try:
        if "xvideos.com" in domain:
            print(f"[*] Detectado link do Xvideos. Iniciando extração...")
            scraper = XvideosScraper()
            return scraper.scrape(url)
            
        elif "erome.com" in domain:
            print(f"[*] Detectado link do Erome. Iniciando extração...")
            scraper = EromeScraper()
            return scraper.scrape(url)
            
        else:
            return {"erro": "Domínio não suportado. Insira um link do Xvideos ou Erome."}
            
    except requests.exceptions.RequestException as e:
        return {"erro": f"Falha na conexão HTTP: {str(e)}"}
    except Exception as e:
        return {"erro": f"Erro inesperado ao processar: {str(e)}"}

if __name__ == "__main__":
    import os
    import json
    
    link_input = None

    # 1. TENTA LER O PAYLOAD DO FRONTEND (Netlify)
    config_data_env = os.environ.get('CONFIG_DATA')
    if config_data_env:
        try:
            # Converte o pacote de texto do front em um dicionário Python
            config_data = json.loads(config_data_env)
            
            # Aqui ele busca a chave onde o link foi salvo. 
            # Dependendo de como seu front foi programado, pode ser 'url_scraping', 'url', ou 'link'
            link_input = config_data.get('url_scraping') or config_data.get('url') or config_data.get('link')
            
            print("[*] Comando recebido com sucesso pelo painel Sniper Control!")
            
        except json.JSONDecodeError:
            print("[!] Erro: O formato de dados enviado pelo frontend é inválido.")

    # 2. SE NÃO VEIO DO FRONT, TENTA LER O MODO MANUAL (GitHub Actions)
    if not link_input and len(sys.argv) > 1:
        link_input = sys.argv[1].strip()
        print("[*] Comando manual recebido via terminal/GitHub.")

    # 3. SE NÃO ACHAR O LINK EM NENHUM LUGAR, ENCERRA.
    if not link_input:
        print("[!] Erro: Nenhum link fornecido pelo Frontend ou Terminal.")
        sys.exit(1)

    # SEGUE COM O SCRAPING
    print(f"\n[*] Iniciando extração para: {link_input}")
    resultado = processar_link(link_input)
    
    print("\n--- RESULTADO ---")
    for chave, valor in resultado.items():
        if isinstance(valor, list):
            print(f"{chave.capitalize()}:")
            for item in valor:
                print(f"  -> {item}")
        else:
            print(f"{chave.capitalize()}: {valor}")
    print("-" * 17)
