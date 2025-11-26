import os
import subprocess
import sys
import numpy as np
import pandas as pd
import csv
from pathlib import Path

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

ensure_pkg("transformers")
ensure_pkg("sentence_transformers")
ensure_pkg("torch")
ensure_pkg("pandas")
ensure_pkg("numpy")

# ================================================================
# IMPORTAÇÕES
# ================================================================
from transformers import pipeline
from sentence_transformers import SentenceTransformer, util
import torch

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
# CSV
# ================================================================
def carregar_csv(caminho="musicas.csv"):
    print(f"[INFO] Lendo CSV: {caminho}")
    df = pd.read_csv(caminho)
    df["titulo"] = df["titulo"].str.lower()
    return df

# ================================================================
# BUSCAR LETRA
# ================================================================
def buscar_letra(df, nome_musica):
    nome_musica = nome_musica.lower()
    resultado = df[df["titulo"] == nome_musica]

    if len(resultado) == 0:
        print(f"[ERRO] Música '{nome_musica}' não encontrada.")
        return None

    return resultado.iloc[0]["letra"]

# ================================================================
# SIMILARIDADE
# ================================================================
def comparar_letras(sim_model, letra_original, letra_usuario):
    versos_original = [v.strip() for v in letra_original.split("\n") if v.strip()]
    versos_usuario = [v.strip() for v in letra_usuario.split("\n") if v.strip()]

    if len(versos_usuario) == 0:
        versos_usuario = [letra_usuario]

    emb_original = sim_model.encode(versos_original, convert_to_tensor=True)
    emb_usuario = sim_model.encode(versos_usuario, convert_to_tensor=True)

    matriz_sim = util.cos_sim(emb_original, emb_usuario)

    melhor_por_linha = [float(torch.max(linha)) for linha in matriz_sim]
    media_sim = float(np.mean(melhor_por_linha))

    return media_sim, melhor_por_linha, versos_original

# ================================================================
# GERAR RELATÓRIO CSV
# ================================================================
def gerar_relatorio_csv(relatorio_path, versos_original, versos_usuario, scores):
    Path(relatorio_path).parent.mkdir(parents=True, exist_ok=True)

    pares = list(zip(versos_original, versos_usuario, scores))
    pares_ordenados = sorted(pares, key=lambda x: x[2], reverse=True)

    top_mais = pares_ordenados[:5]
    top_menos = pares_ordenados[-5:]

    with open(relatorio_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        writer.writerow(["Tipo", "Original", "Usuário", "Similaridade"])

        for item in top_mais:
            writer.writerow(["MAIOR", item[0], item[1], f"{item[2]:.4f}"])

        for item in top_menos:
            writer.writerow(["MENOR", item[0], item[1], f"{item[2]:.4f}"])

    print(f"[OK] Relatório CSV gerado em: {relatorio_path}")

# ================================================================
# NOTA
# ================================================================
def calcular_nota(sim):
    nota = int(sim * 99)
    return max(0, min(99, nota))

# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    configurar_ffmpeg_local()
    stt, sim = load_models()

    ARQUIVO_AUDIO = "audios/canto.wav"
    NOME_MUSICA = "The Search"

    df = carregar_csv()
    letra_original = buscar_letra(df, NOME_MUSICA)

    if letra_original is None:
        sys.exit()

    texto_usuario = transcrever_audio(stt, ARQUIVO_AUDIO)

    media_sim, lista_sim, versos = comparar_letras(sim, letra_original, texto_usuario)
    nota_final = calcular_nota(media_sim)

    print("\n================= RELATÓRIO FINAL =================\n")
    print(f"Música: {NOME_MUSICA}")
    print(f"Nota geral: {nota_final}/99")
    print(f"Similaridade média: {media_sim:.3f}\n")

    print("Resultados por verso:\n")
    for verso, score in zip(versos, lista_sim):
        print(f"- \"{verso}\" -> {score:.3f}")

    print("\n====================================================\n")

    gerar_relatorio_csv(
        "relatorios/feedback.csv",
        versos_original=versos,
        versos_usuario=[texto_usuario] * len(versos),
        scores=lista_sim
    )
