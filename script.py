import os
import subprocess
import sys
import numpy as np
import pandas as pd
import csv
from pathlib import Path
import unicodedata
import re

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
# CARREGAR CSV
# ================================================================
def carregar_csv_palavras(caminho="musicas.csv"):
    print(f"[INFO] Lendo CSV de palavras: {caminho}")
    df = pd.read_csv(caminho)
    df["titulo"] = df["titulo"].str.lower()
    return df


# ================================================================
# LETRA ORIGINAL
# ================================================================
def montar_letra_por_palavras(df, nome_musica):
    nome_musica = nome_musica.lower()
    linhas = df[df["titulo"] == nome_musica]

    if len(linhas) == 0:
        print(f"[ERRO] Música '{nome_musica}' não encontrada.")
        return None

    palavras = linhas["palavra"].tolist()
    return palavras


# ================================================================
# ALINHAR
# ================================================================
def alinhar_palavras(lista_original, lista_usuario):
    alinhado_usuario = []
    idx = 0

    for palavra in lista_original:
        if idx < len(lista_usuario):
            alinhado_usuario.append(lista_usuario[idx])
            idx += 1
        else:
            alinhado_usuario.append("")

    return alinhado_usuario


# ================================================================
# NORMALIZAÇÃO
# ================================================================
def normalizar_texto_lista(palavras):
    texto = " ".join(palavras)
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    texto = re.sub(r'[^a-zA-Z0-9\s]', ' ', texto)
    return texto.split()


# ================================================================
# DETECTAR PALAVRAS NÃO CANTADAS
# ================================================================
def detectar_palavras_faltantes(palavras_original, palavras_transcritas):
    lista_original_norm = normalizar_texto_lista(palavras_original)
    lista_transcrita_norm = normalizar_texto_lista(palavras_transcritas)

    set_original = set(lista_original_norm)
    set_transcrita = set(lista_transcrita_norm)

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
    emb_original = sim_model.encode(palavras_original, convert_to_tensor=True)

    palavras_usuario_tratadas = [
        p if p.strip() != "" else "[EMPTY]" for p in palavras_usuario
    ]

    emb_usuario = sim_model.encode(palavras_usuario_tratadas, convert_to_tensor=True)

    matriz = util.cos_sim(emb_original, emb_usuario)

    melhor_por_palavra = [
        float(torch.max(linha)) if palavras_usuario[i].strip() != "" else 0.0
        for i, linha in enumerate(matriz)
    ]

    media = float(np.mean(melhor_por_palavra))

    return media, melhor_por_palavra


# ================================================================
# GERAR RELATÓRIO CSV
# ================================================================
def gerar_relatorio_csv(relatorio_path, palavras_original, palavras_usuario, scores, info_faltantes):
    Path(relatorio_path).parent.mkdir(parents=True, exist_ok=True)

    pares = list(zip(palavras_original, palavras_usuario, scores))
    pares_ordenados = sorted(pares, key=lambda x: x[2], reverse=True)

    top_mais = pares_ordenados[:10]
    top_menos = pares_ordenados[-10:]

    with open(relatorio_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")

        writer.writerow(["Cobertura (%)", info_faltantes["cobertura"]])
        writer.writerow(["Total na letra", info_faltantes["total_original"]])
        writer.writerow(["Total transcrito", info_faltantes["total_transcrito"]])
        writer.writerow([])
        writer.writerow(["Palavras não cantadas"])
        writer.writerow(info_faltantes["faltantes"])
        writer.writerow([])

        writer.writerow(["Tipo", "Original", "Usuário", "Similaridade"])

        for item in top_mais:
            writer.writerow(["MAIOR", item[0], item[1], f"{item[2]:.4f}"])

        for item in top_menos:
            writer.writerow(["MENOR", item[0], item[1], f"{item[2]:.4f}"])

        writer.writerow([])
        writer.writerow(["LISTA COMPLETA"])
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
# MAIN
# ================================================================
if __name__ == "__main__":
    configurar_ffmpeg_local()
    stt, sim = load_models()

    ARQUIVO_AUDIO = "audios/canto.wav"
    NOME_MUSICA = "The Search"

    df = carregar_csv_palavras()
    palavras_original = montar_letra_por_palavras(df, NOME_MUSICA)

    if palavras_original is None:
        sys.exit()

    texto_usuario = transcrever_audio(stt, ARQUIVO_AUDIO)
    palavras_usuario = texto_usuario.split()

    palavras_usuario_alinhadas = alinhar_palavras(palavras_original, palavras_usuario)

    media_sim, scores = comparar_palavras(sim, palavras_original, palavras_usuario_alinhadas)
    nota_final = calcular_nota(media_sim)

    info_faltantes = detectar_palavras_faltantes(palavras_original, palavras_usuario)

    print("\n================= RELATÓRIO FINAL =================\n")
    print(f"Música: {NOME_MUSICA}")
    print(f"Nota geral: {nota_final}/99")
    print(f"Similaridade média: {media_sim:.3f}\n")

    print(f"Palavras não cantadas: {len(info_faltantes['faltantes'])}")
    print(f"Cobertura do áudio sobre a letra: {info_faltantes['cobertura']}%\n")

    print("As primeiras comparações:\n")

    for o, u, sc in zip(palavras_original[:20], palavras_usuario_alinhadas[:20], scores[:20]):
        print(f"- {o}  <>  {u if u != '' else '[NÃO CANTADA]'}  -> {sc:.3f}")

    print("\n====================================================\n")

    gerar_relatorio_csv(
        "relatorios/feedback_palavras.csv",
        palavras_original,
        palavras_usuario_alinhadas,
        scores,
        info_faltantes
    )
