import csv
import re
import os
from ytmusicapi import YTMusic # Importamos a biblioteca

# --- Configuração ---
ARQUIVO_CSV_GLOBAL = "musicas.csv"

def buscar_letra_ytmusic(titulo, artista):
    """
    Busca a letra no YouTube Music usando ytmusicapi.
    Retorna a string da letra ou None se não encontrar.
    """
    yt = YTMusic()
    termo_busca = f"{titulo} {artista}"
    
    # Busca a música (filtro por 'songs')
    resultados = yt.search(termo_busca, filter="songs")
    
    if not resultados:
        # print("[!] Nenhuma música encontrada.") # Comentado para não poluir o log do servidor
        return None

    video_id = resultados[0]['videoId']
    
    # 2. Obter o objeto 'watch playlist' que contém o ID da letra
    watch_playlist = yt.get_watch_playlist(videoId=video_id)
    
    lyrics_id = watch_playlist.get('lyrics')
    
    if not lyrics_id:
        return None

    # 3. Buscar o conteúdo da letra com o ID encontrado
    lyrics_data = yt.get_lyrics(lyrics_id)
    
    lyrics_text = lyrics_data.get('lyrics', '')
    
    return lyrics_text

def gerar_csv_palavras(titulo, artista, letra, arquivo_csv=ARQUIVO_CSV_GLOBAL):
    """
    Processa a letra e ADICIONA as palavras ao arquivo CSV usando modo 'a'.
    """
    # Sua regex original
    palavras = re.findall(r"\b\w+'\w+|\w+\b", letra)

    # Verifica se o arquivo existe para saber se deve escrever o cabeçalho
    escrever_cabecalho = not os.path.exists(arquivo_csv)
    
    try:
        # Modo "a" (append) para adicionar ao arquivo existente ou criar um novo.
        with open(arquivo_csv, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            
            if escrever_cabecalho:
                writer.writerow(["id", "titulo", "artista", "palavra"])

            for idx, palavra in enumerate(palavras, 1):
                writer.writerow([idx, titulo, artista, palavra])

        # print(f"[OK] {len(palavras)} palavras salvas em: {os.path.abspath(arquivo_csv)}")
        return True
        
    except Exception as e:
        print(f"[Erro CSV] Falha ao escrever no CSV para '{titulo}': {e}")
        return False


def buscar_e_adicionar_letra(titulo, artista, arquivo_csv=ARQUIVO_CSV_GLOBAL):
    """
    Função principal a ser chamada pelo servidor.py.
    Tenta buscar a letra e, se encontrar, adiciona ao CSV.
    Retorna True em caso de sucesso.
    """
    print(f"[LETRA BUSCA] Tentando buscar letra: {titulo} - {artista}")
    letra_encontrada = buscar_letra_ytmusic(titulo, artista)
    
    if letra_encontrada:
        print("[LETRA BUSCA] Letra encontrada. Salvando no CSV.")
        return gerar_csv_palavras(titulo, artista, letra_encontrada, arquivo_csv)
    else:
        print("[LETRA BUSCA] Letra não disponível no YT Music.")
        return False

if __name__ == "__main__":
    # Mantemos o bloco principal apenas para testes isolados do script
    print("--- Teste Rápido de Busca de Letra ---")
    titulo = input("Digite o título da música: ").strip()
    artista = input("Digite o artista: ").strip()
    
    if titulo and artista:
        sucesso = buscar_e_adicionar_letra(titulo, artista)
        if sucesso:
            print(f"\n[SUCESSO] Letra de {titulo} foi salva em {ARQUIVO_CSV_GLOBAL}.")
        else:
            print("\n[FALHA] Não foi possível encontrar ou salvar a letra.")