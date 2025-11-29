import os
import subprocess
import sys
import numpy as np
import pandas as pd
import csv
from pathlib import Path
import unicodedata
import re
import torch

# Importar a função do módulo externo. Certifique-se de que 'letras_csv.py'
# está no mesmo diretório ou no seu PYTHONPATH.
# Esta função deve buscar a letra e adicioná-la ao CSV se for encontrada.
try:
    from letras_csv import buscar_e_adicionar_letra
except ImportError:
    print("[ERRO FATAL] Não foi possível importar 'buscar_e_adicionar_letra' do módulo 'letras_csv.py'. Verifique se o arquivo existe e está configurado corretamente.")
    sys.exit(1)


# ================================================================
# CONFIGURAR FFMPEG LOCALMENTE
# ================================================================
def configurar_ffmpeg_local():
    ffmpeg_local = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")

    if not os.path.exists(ffmpeg_local):
        print("[ERRO] ffmpeg.exe não encontrado na pasta ./ffmpeg/")
        return

    os.environ["FFMPEG_BINARY"] = ffmpeg_local
    os.environ["PATH"] = os.path.dirname(ffmpeg_local) + os.pathsep + os.environ["PATH"]
    print(f"[INFO] ffmpeg configurado: {ffmpeg_local}\n")


# ================================================================
# INSTALAR PACOTES
# ================================================================
def ensure_pkg(pkg):
    try:
        __import__(pkg)
    except ImportError:
        print(f"[INFO] Instalando {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        print(f"[INFO] {pkg} instalado.\n")

# Garante que os pacotes essenciais para o script principal estejam instalados
ensure_pkg("transformers")
ensure_pkg("sentence_transformers")
ensure_pkg("torch")
ensure_pkg("pandas")
ensure_pkg("numpy")


from transformers import pipeline
from sentence_transformers import SentenceTransformer, util


# ================================================================
# CARREGAR MODELOS
# ================================================================
def load_models():
    print("[INFO] Carregando Whisper...")
    stt = pipeline(
        task="automatic-speech-recognition",
        model="openai/whisper-small",
        device=0 if torch.cuda.is_available() else -1
    )

    print("[INFO] Carregando SBERT...")
    sim = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    print("[INFO] Modelos carregados.\n")
    return stt, sim


# ================================================================
# TRANSCRIÇÃO
# ================================================================
def transcrever_audio(stt_model, audio_path):
    print(f"[INFO] Transcrevendo: {audio_path}")

    resultado = stt_model(
        audio_path,
        return_timestamps=True,
        chunk_length_s=30,
        batch_size=8
    )

    texto = resultado["text"]
    print(f"[INFO] Transcrição concluída.")
    return texto


# ================================================================
# CARREGAR CSV
# ================================================================
def carregar_csv_palavras(caminho="musicas.csv"):
    print(f"[INFO] Lendo CSV de palavras: {caminho}")
    # O `engine='python'` pode ser necessário para pandas ler arquivos de tamanho misto
    df = pd.read_csv(caminho, encoding="utf-8") 
    df["titulo"] = df["titulo"].str.lower()
    return df


# ================================================================
# LETRA ORIGINAL
# ================================================================
def montar_letra_por_palavras(df, nome_musica):
    nome_musica = nome_musica.lower()
    linhas = df[df["titulo"] == nome_musica]

    if len(linhas) == 0:
        # Retorna None para indicar que a música não está no CSV
        print(f"[AVISO] Música '{nome_musica}' não encontrada no CSV.")
        return None

    palavras = linhas["palavra"].tolist()
    return palavras


# ================================================================
# NORMALIZAÇÃO
# ================================================================
def normalizar_texto_lista(palavras):
    texto = " ".join(palavras)
    texto = texto.lower()
    # Remove acentos
    texto = ''.join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    # Remove tudo que não for letra, número ou espaço
    texto = re.sub(r'[^a-zA-Z0-9\s]', ' ', texto) 
    return texto.split()


# ================================================================
# ALINHAMENTO INTELIGENTE (NEEDLEMAN–WUNSCH)
# Implementa o alinhamento de sequência com base na similaridade SBERT
# ================================================================
def alinhar_inteligente(sim_model, original, transcrito):
    # Apenas a parte central do seu algoritmo de alinhamento
    o = normalizar_texto_lista(original)
    t = normalizar_texto_lista(transcrito)

    if not o or not t:
        print("[AVISO] Texto original ou transcrito vazio, pulando alinhamento.")
        return [], []

    emb_o = sim_model.encode(o, convert_to_tensor=True)
    emb_t = sim_model.encode(t, convert_to_tensor=True)

    sim_matrix = util.cos_sim(emb_o, emb_t).cpu().numpy()

    gap = -0.4
    n, m = len(o), len(t)

    score = np.zeros((n+1, m+1))
    path = np.zeros((n+1, m+1), dtype=int)

    # Inicialização das bordas
    for i in range(1, n+1):
        score[i][0] = i * gap
        path[i][0] = 1 # Delete (Gap na Transcrição)

    for j in range(1, m+1):
        score[0][j] = j * gap
        path[0][j] = 2 # Insert (Gap na Original)

    # Preenchimento da matriz
    for i in range(1, n+1):
        for j in range(1, m+1):
            match = score[i-1][j-1] + sim_matrix[i-1][j-1]
            delete = score[i-1][j] + gap
            insert = score[i][j-1] + gap

            melhor = max(match, delete, insert)

            score[i][j] = melhor

            if melhor == match:
                path[i][j] = 0 # Match/Mismatch
            elif melhor == delete:
                path[i][j] = 1 # Delete
            else:
                path[i][j] = 2 # Insert

    # Reconstrução do caminho (Backtracking)
    i, j = n, m
    alinhado_o = []
    alinhado_t = []

    while i > 0 or j > 0:
        if i > 0 and j > 0 and path[i][j] == 0:
            alinhado_o.append(o[i-1])
            alinhado_t.append(t[j-1])
            i -= 1
            j -= 1
        elif i > 0 and path[i][j] == 1:
            alinhado_o.append(o[i-1])
            alinhado_t.append("")
            i -= 1
        else:
            alinhado_o.append("")
            alinhado_t.append(t[j-1])
            j -= 1

    alinhado_o.reverse()
    alinhado_t.reverse()

    return alinhado_o, alinhado_t


# ================================================================
# DETECTAR PALAVRAS NÃO CANTADAS
# ================================================================
def detectar_palavras_faltantes(palavras_original, palavras_transcritas):
    lista_original_norm = normalizar_texto_lista(palavras_original)
    lista_transcrita_norm = normalizar_texto_lista(palavras_transcritas)

    set_original = set(lista_original_norm)
    set_transcrita = set(lista_transcrita_norm)

    # Palavras que estão na letra original mas não no áudio transcrito
    faltantes = [w for w in lista_original_norm if w not in set_transcrita]

    cobertura = (len(set_original & set_transcrita) / len(set_original)) * 100 if len(set_original) > 0 else 0

    return {
        "cobertura": round(cobertura, 2),
        "faltantes": faltantes,
        "total_original": len(lista_original_norm),
        "total_transcrito": len(lista_transcrita_norm)
    }


# ================================================================
# COMPARAR PALAVRAS
# ================================================================
def comparar_palavras(sim_model, palavras_original, palavras_usuario):
    # Encodar a letra original
    emb_original = sim_model.encode(palavras_original, convert_to_tensor=True)

    # Tratar palavras vazias no usuário antes de encodar
    palavras_usuario_tratadas = [
        p if p.strip() != "" else "[EMPTY]" for p in palavras_usuario
    ]
    emb_usuario = sim_model.encode(palavras_usuario_tratadas, convert_to_tensor=True)

    # Matriz de similaridade (o x u)
    matriz = util.cos_sim(emb_original, emb_usuario)

    # Pega o score mais alto de similaridade para cada palavra original
    melhor_por_palavra = [
        float(torch.max(linha)) if palavras_usuario[i].strip() != "" else 0.0
        for i, linha in enumerate(matriz)
    ]

    # Média geral de similaridade
    media = float(np.mean(melhor_por_palavra))

    return media, melhor_por_palavra

# A função `executar_analise` original foi incorporada ao `if __name__ == "__main__"` para simplificar.

# ================================================================
# GERAR RELATÓRIO CSV
# ================================================================
def gerar_relatorio_csv(relatorio_path, palavras_original, palavras_usuario, scores, info_faltantes):
    Path(relatorio_path).parent.mkdir(parents=True, exist_ok=True)

    # ... (Sua lógica de relatório CSV original) ...
    pares = list(zip(palavras_original, palavras_usuario, scores))
    pares_ordenados = sorted(pares, key=lambda x: x[2], reverse=True)

    # Exclui pares vazios/não cantados do ranking de notas
    pares_sem_vazios = [p for p in pares_ordenados if p[1].strip() != ""]
    
    top_mais = pares_sem_vazios[:10]
    top_menos = pares_sem_vazios[-10:]

    with open(relatorio_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        writer.writerow(["Métrica", "Valor"])
        writer.writerow(["Cobertura (%)", info_faltantes["cobertura"]])
        writer.writerow(["Total na letra", info_faltantes["total_original"]])
        writer.writerow(["Total transcrito", info_faltantes["total_transcrito"]])
        writer.writerow([])
        
        writer.writerow(["Palavras não cantadas (Lista)"])
        writer.writerow([""] + info_faltantes["faltantes"])
        writer.writerow([])

        writer.writerow(["Tipo", "Original", "Usuário", "Similaridade"])

        writer.writerow(["--- Top 10 MAIOR Similaridade ---"])
        for item in top_mais:
            writer.writerow(["MAIOR", item[0], item[1], f"{item[2]:.4f}"])

        writer.writerow(["--- Top 10 MENOR Similaridade ---"])
        for item in top_menos:
            writer.writerow(["MENOR", item[0], item[1], f"{item[2]:.4f}"])

        writer.writerow([])
        writer.writerow(["LISTA COMPLETA ALINHADA"])
        writer.writerow(["Original", "Usuário", "Similaridade"])

        for o, u, s in pares:
            writer.writerow([o, u, f"{s:.4f}"])

    print(f"[OK] Relatório CSV gerado em: {relatorio_path}")


# ================================================================
# NOTA
# ================================================================
def calcular_nota(sim):
    nota = int(sim * 99)
    return max(0, min(99, nota))


# ================================================================
# MAIN (Ponto de entrada do script)
# ================================================================
if __name__ == "__main__":
    configurar_ffmpeg_local()

    # --- Configurações da Análise ---
    ARQUIVO_CSV_LETRAS = "musicas.csv"
    ARQUIVO_AUDIO = "audios/canto.wav"
    NOME_MUSICA = "The Search" 
    # [IMPORTANTE] Defina o artista para o caso de a busca ser necessária
    ARTISTA = "NF" 
    # --------------------------------

    palavras_original = None
    
    # 1. Tentar carregar a letra do CSV local
    try:
        df = carregar_csv_palavras(ARQUIVO_CSV_LETRAS)
        palavras_original = montar_letra_por_palavras(df, NOME_MUSICA)
    except FileNotFoundError:
        print(f"[AVISO] O arquivo CSV '{ARQUIVO_CSV_LETRAS}' não foi encontrado. Tentando buscar a letra...")
        
    # 2. Se a música não foi encontrada no CSV, buscar no YT Music
    if palavras_original is None:
        print(f"[BUSCA] Buscando '{NOME_MUSICA}' de '{ARTISTA}' online...")
        sucesso_busca = buscar_e_adicionar_letra(NOME_MUSICA, ARTISTA, ARQUIVO_CSV_LETRAS)
        
        if sucesso_busca:
            # Se a busca funcionou e a letra foi adicionada, recarrega o CSV
            print("[INFO] Recarregando CSV com a nova letra...")
            df = carregar_csv_palavras(ARQUIVO_CSV_LETRAS)
            palavras_original = montar_letra_por_palavras(df, NOME_MUSICA)
        else:
            print(f"[ERRO FATAL] Não foi possível encontrar a letra para '{NOME_MUSICA}' localmente ou online.")
            sys.exit(1) # Sai do script, pois não há letra para comparar

    # Neste ponto, `palavras_original` DEVE conter a letra.
    
    # 3. Carregar modelos e iniciar a análise
    print("[INFO] Letra pronta. Carregando modelos e iniciando a transcrição...")
    stt, sim = load_models()

    texto_usuario = transcrever_audio(stt, ARQUIVO_AUDIO)
    palavras_usuario = texto_usuario.split()

    # 4. Processamento e Alinhamento
    palavras_alinh_o, palavras_alinh_u = alinhar_inteligente(sim, palavras_original, palavras_usuario)

    # 5. Comparação e Resultados
    media_sim, scores = comparar_palavras(sim, palavras_alinh_o, palavras_alinh_u)
    nota_final = calcular_nota(media_sim)

    info_faltantes = detectar_palavras_faltantes(palavras_original, palavras_usuario)

    print("\n================= RELATÓRIO FINAL =================\n")
    print(f"Música: **{NOME_MUSICA}**")
    print(f"Nota geral: **{nota_final}/99**")
    print(f"Similaridade média: **{media_sim:.3f}**\n")

    print(f"Palavras não cantadas (exclusivas da letra): {len(info_faltantes['faltantes'])}")
    print(f"Cobertura do áudio sobre a letra: **{info_faltantes['cobertura']}%**\n")

    print("As primeiras comparações (Original <> Transcrito):\n")

    for o, u, sc in zip(palavras_alinh_o[:20], palavras_alinh_u[:20], scores[:20]):
        # Formata a saída para melhor visualização
        user_word = u if u != '' else '[NÃO CANTADA]'
        print(f"- **{o:<20}** <> **{user_word:<15}** -> {sc:.3f}")

    print("\n====================================================\n")

    # 6. Gerar Relatório
    gerar_relatorio_csv(
        "relatorios/feedback_palavras.csv",
        palavras_alinh_o,
        palavras_alinh_u,
        scores,
        info_faltantes
    )