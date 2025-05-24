import os
import random
import requests
import fitz
from googlesearch import search
import re
from colorama import init, Fore, Style
import time
import csv
import logging
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

init(autoreset=True)

if not os.path.exists('cv_results'):
    os.mkdir('cv_results')

logging.basicConfig(filename='cvfinder_errors.log', level=logging.ERROR)

def intro():
    print(f"\n{Fore.CYAN}{'='*40}")
    print(""" 
 ██████╗██╗   ██╗███████╗██╗███╗   ██╗██████╗ ███████╗██████╗        ██████╗██╗  ██╗███████╗
██╔════╝██║   ██║██╔════╝██║████╗  ██║██╔══██╗██╔════╝██╔══██╗      ██╔════╝╚██╗██╔╝██╔════╝
██║     ██║   ██║█████╗  ██║██╔██╗ ██║██║  ██║█████╗  ██████╔╝█████╗██║      ╚███╔╝ ███████╗
██║     ╚██╗ ██╔╝██╔══╝  ██║██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗╚════╝██║      ██╔██╗ ╚════██║
╚██████╗ ╚████╔╝ ██║     ██║██║ ╚████║██████╔╝███████╗██║  ██║      ╚██████╗██╔╝ ██╗███████║
 ╚═════╝  ╚═══╝  ╚═╝     ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝       ╚═════╝╚═╝  ╚═╝╚══════╝
                                   https://t.me.theCxsgroup                                                     
          """)
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Style.DIM}Recherche automatique de CVs publics (PDF, LinkedIn, etc.)\n")

def get_proxies_from_file(file_path):
    proxies = []
    try:
        with open(file_path, 'r') as file:
            proxies = [line.strip() for line in file.readlines() if line.strip()]
    except Exception as e:
        print(f"{Fore.RED}[!] Erreur lors de la lecture du fichier de proxies : {e}")
        logging.error(f"Erreur lors de la lecture du fichier de proxies : {e}")
    return proxies

def get_random_proxy(proxies):
    if proxies:
        return random.choice(proxies)
    return None

def make_request(url, proxies=None, **kwargs):
    proxy = get_random_proxy(proxies) if proxies else None
    proxies_dict = {
        "http": proxy,
        "https": proxy,
    } if proxy else None

    try:
        response = requests.get(url, proxies=proxies_dict, **kwargs)
        return response
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur avec le proxy {proxy} pour {url}: {e}")
        return None

def build_dorks(name=None, email=None):
    base = f'"{name}"' if name else f'"{email}"'
    dorks = [
        f'{base} ("CV" OR "curriculum vitae") filetype:pdf site:.fr',
        f'{base} filetype:pdf site:fr.linkedin.com',
        f'{base} intitle:"cv" filetype:pdf',
        f'{base} site:welcometothejungle.com',
        f'{base} site:pole-emploi.fr "curriculum vitae" filetype:pdf',
        f'{base} site:academia.edu filetype:pdf',
        f'{base} site:researchgate.net filetype:pdf',
        f'{base} site:dropbox.com/s/ filetype:pdf',
        f'{base} site:drive.google.com filetype:pdf',
        f'{base} ("CV" OR "curriculum vitae") filetype:pdf after:2023',
        f'{base} ("CV" OR "curriculum vitae") filetype:pdf site:github.com',
        f'{base} ("CV" OR "curriculum vitae") filetype:pdf site:cv-library.co.uk',
    ]
    return dorks

def search_google_dorks(dorks, max_links=5, proxies=None):
    urls = []
    for query in dorks:
        print(f"{Fore.YELLOW}[?] Requête : {Style.BRIGHT}{query}")
        try:
            results = list(search(query, num_results=max_links)) 
            urls.extend(results)
        except Exception as e:
            print(f"{Fore.RED}[!] Erreur Google Search : {e}")
    return list(set(urls))

def download_pdf(url, proxies=None):
    attempts = 3
    for attempt in range(attempts):
        try:
            r = make_request(url, proxies=proxies, timeout=10)
            if r and r.status_code == 200 and "pdf" in r.headers.get('Content-Type', ''):
                file_name = url.split("/")[-1].split('?')[0]
                if not file_name.endswith(".pdf"):
                    file_name += ".pdf"
                path = f'cv_results/{file_name}'
                with open(path, 'wb') as f:
                    f.write(r.content)
                print(f"{Fore.GREEN}[+] PDF téléchargé : {file_name}")
                return path
        except Exception as e:
            print(f"{Fore.RED}[!] Erreur téléchargement (tentative {attempt + 1}): {e}")
            logging.error(f"Erreur téléchargement {url} (tentative {attempt + 1}): {e}")
            if attempt < attempts - 1:
                print(f"Réessayer dans 5 secondes...")
                time.sleep(5)
    return None

def extract_pdf_info(filepath):
    try:
        doc = fitz.open(filepath)
        text = "".join(page.get_text() for page in doc)
        doc.close()

        return {
            "email": list(set(re.findall(r"[a-zA-Z0-9.\-_]+@[a-zA-Z0-9\-_]+\.[a-zA-Z.]+", text))),
            "phone": list(set(re.findall(r"0[1-9](?:[\s.-]?\d{2}){4}", text))),
            "salary": list(set(re.findall(r"\d{2,3}\s?(?:k|K|000)?\s?€", text))),
            "text": text[:800]
        }
    except Exception as e:
        print(f"{Fore.RED}[!] Erreur extraction PDF : {e}")
        logging.error(f"Erreur extraction PDF : {e}")
        return {}

def generate_csv_report(results, name_or_email):
    filename = f'cv_results/rapport_{name_or_email.replace(" ", "_").replace("@", "_")}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['URL', 'File', 'Email', 'Phone', 'Salary', 'Excerpt'])
        for res in results:
            writer.writerow([res['url'], res['file'], ', '.join(res['info'].get('email', [])),
                             ', '.join(res['info'].get('phone', [])), ', '.join(res['info'].get('salary', [])),
                             res['info'].get('text', '')[:200]])
    print(f"\n{Fore.BLUE}[✔] Rapport CSV sauvegardé : {Style.BRIGHT}{filename}")

def run_cvfinder(name=None, email=None, proxies=None):
    dorks = build_dorks(name, email)
    print(f"{Fore.MAGENTA}Recherche en cours...\n")
    urls = search_google_dorks(dorks, proxies=proxies)
    results = []

    for url in urls:
        if ".pdf" in url:
            print(f"{Fore.CYAN}[~] Tentative de téléchargement : {url}")
            pdf_path = download_pdf(url, proxies=proxies)
            if pdf_path:
                info = extract_pdf_info(pdf_path)

                if info:
                    results.append({
                        "url": url,
                        "file": os.path.basename(pdf_path),
                        "info": info
                    })

    if results:
        generate_csv_report(results, name or email)
    else:
        print(f"{Fore.RED}[!] Aucun CV trouvé...")

if __name__ == "__main__":
    intro()
    use_proxies = input("Souhaitez-vous utiliser des proxies ? (y/n) : ").strip().lower()
    
    proxies = []
    if use_proxies == "y":
        proxies_path = input("Entrez le chemin vers le fichier contenant les proxies : ").strip()
        proxies = get_proxies_from_file(proxies_path)
        if not proxies:
            print(f"{Fore.RED}[!] Aucun proxy valide trouvé dans le fichier.")

    choice = input("🔎 Recherche par (1) Nom/Prénom ou (2) Email ? [1/2] : ")

    if choice.strip() == "1":
        name = input("Entrez le nom complet (ex: Jean Dupont) : ")
        run_cvfinder(name=name.strip(), proxies=proxies)
    elif choice.strip() == "2":
        email = input("Entrez l'email (ex: jean.dupont@gmail.com) : ")
        run_cvfinder(email=email.strip(), proxies=proxies)
    else:
        print(f"{Fore.RED}Choix invalide.")
