# Importações necessárias para a API
import os
import json
import requests
from base64 import b64encode
from dotenv import load_dotenv, find_dotenv
from flask import Flask, Response

# Carrega as variáveis de ambiente (SPOTIFY_CLIENT_ID, etc.)
load_dotenv(find_dotenv())

# --- Constantes da API do Spotify ---
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET_ID = os.getenv("SPOTIFY_SECRET_ID")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")

REFRESH_TOKEN_URL = "https://accounts.spotify.com/api/token"
NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
RECENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=1"

# Variável global para armazenar o token de acesso
SPOTIFY_TOKEN = ""

# Inicia a aplicação Flask
app = Flask(__name__)

# --- Funções de Autenticação com o Spotify ---

def get_auth():
    """Gera o cabeçalho de autorização Basic."""
    return b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_SECRET_ID}".encode()).decode("ascii")

def refresh_token():
    """Atualiza o token de acesso usando o refresh token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": SPOTIFY_REFRESH_TOKEN,
    }
    headers = {"Authorization": f"Basic {get_auth()}"}
    response = requests.post(REFRESH_TOKEN_URL, data=data, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Erro ao atualizar token: {response.text}")
        
    return response.json()["access_token"]

def get_spotify_data(url):
    """Faz uma requisição GET para a API do Spotify, atualizando o token se necessário."""
    global SPOTIFY_TOKEN

    if not SPOTIFY_TOKEN:
        SPOTIFY_TOKEN = refresh_token()

    headers = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}
    response = requests.get(url, headers=headers)

    # Se o token expirou (401), atualiza e tenta de novo
    if response.status_code == 401:
        SPOTIFY_TOKEN = refresh_token()
        headers = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}
        response = requests.get(url, headers=headers)
    
    # Se a resposta estiver vazia (204 No Content), significa que nada está tocando
    if response.status_code == 204:
        return None

    return response.json()

# --- Rota Principal da API ---

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    try:
        # 1. Tenta buscar a música que está tocando agora
        now_playing_data = get_spotify_data(NOW_PLAYING_URL)

        # Se a resposta não for vazia e algo estiver tocando...
        if now_playing_data and now_playing_data.get("is_playing"):
            item = now_playing_data["item"]
            is_playing = True
        else:
            # 2. Se não, busca a última música tocada
            recently_played_data = get_spotify_data(RECENTLY_PLAYING_URL)
            item = recently_played_data["items"][0]["track"]
            is_playing = False

        # 3. Extrai as informações necessárias para o widget
        response_data = {
            "isPlaying": is_playing,
            "title": item["name"],
            "artist": item["artists"][0]["name"],
            "albumImageUrl": item["album"]["images"][0]["url"],  # Usa a imagem maior
            "songUrl": item["external_urls"]["spotify"]
        }

    except Exception as e:
        # 4. Em caso de qualquer erro, retorna uma mensagem de erro
        response_data = {"isPlaying": False, "error": str(e)}

    # 5. Cria e retorna a resposta final em formato JSON
    json_response = json.dumps(response_data, indent=2) # indent=2 para facilitar a leitura se aberto no navegador
    resp = Response(json_response, mimetype='application/json')
    resp.headers["Cache-Control"] = "s-maxage=1, stale-while-revalidate" # Cache para performance
    return resp
