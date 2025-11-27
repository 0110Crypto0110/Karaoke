import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# ============================================================
# LER FEEDBACK PALAVRAS
# ============================================================
def carregar_feedback(caminho_csv="relatorios/feedback_palavras.csv"):
    """
    Converte o CSV gerado no script principal em um DataFrame utilizável.
    Ignora as seções de resumo e importa apenas a tabela principal.
    """
    linhas = []
    comecou = False

    with open(caminho_csv, "r", encoding="utf-8") as f:
        for linha in f:
            if linha.strip() == "LISTA COMPLETA":
                comecou = True
                next(f)  # pular cabeçalho
                continue

            if comecou:
                partes = linha.strip().split(";")
                if len(partes) == 3:
                    linhas.append(partes)

    df = pd.DataFrame(linhas, columns=["original", "usuario", "similaridade"])
    df["similaridade"] = df["similaridade"].astype(float)

    return df


# ============================================================
# GRÁFICO 1 – Linha completa da similaridade
# ============================================================
def grafico_similaridade(df, saida="graficos/similaridade_total.png"):
    Path(saida).parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(14, 4))
    plt.plot(df["similaridade"], linewidth=1.8)
    plt.title("Similaridade por Palavra (sequência da música)")
    plt.xlabel("Índice da palavra")
    plt.ylabel("Similaridade")
    plt.grid(True, alpha=0.3)

    plt.savefig(saida, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"[OK] Gráfico salvo em: {saida}")


# ============================================================
# GRÁFICO 2 – Barras das 20 piores palavras
# ============================================================
def grafico_piores(df, saida="graficos/piores_palavras.png", n=20):
    Path(saida).parent.mkdir(parents=True, exist_ok=True)

    df_sorted = df.sort_values(by="similaridade", ascending=True).head(n)

    plt.figure(figsize=(12, 6))
    plt.barh(
        df_sorted["original"],
        df_sorted["similaridade"]
    )
    plt.title(f"Piores {n} palavras (menor similaridade)")
    plt.xlabel("Similaridade")
    plt.tight_layout()

    plt.savefig(saida, dpi=200)
    plt.close()
    print(f"[OK] Gráfico salvo em: {saida}")


# ============================================================
# GRÁFICO 3 – Barras das 20 melhores palavras
# ============================================================
def grafico_melhores(df, saida="graficos/melhores_palavras.png", n=20):
    Path(saida).parent.mkdir(parents=True, exist_ok=True)

    df_sorted = df.sort_values(by="similaridade", ascending=False).head(n)

    plt.figure(figsize=(12, 6))
    plt.barh(
        df_sorted["original"],
        df_sorted["similaridade"]
    )
    plt.title(f"Melhores {n} palavras (maior similaridade)")
    plt.xlabel("Similaridade")
    plt.tight_layout()

    plt.savefig(saida, dpi=200)
    plt.close()
    print(f"[OK] Gráfico salvo em: {saida}")


# ============================================================
# EXPORTAR PARA FLUTTER (JSON OU ARRAY)
# ============================================================
def exportar_json(df, caminho="graficos/similaridade.json"):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    df.to_json(caminho, orient="records", force_ascii=False, indent=2)
    print(f"[OK] JSON exportado para Flutter: {caminho}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    df = carregar_feedback()

    grafico_similaridade(df)
    grafico_piores(df)
    grafico_melhores(df)

    exportar_json(df)

''' 
1. Exibindo os gráficos

Basta colocar as imagens geradas (PNG) na pasta assets/ do Flutter:

assets:
  - assets/graficos/similaridade_total.png
  - assets/graficos/piores_palavras.png
  - assets/graficos/melhores_palavras.png
'''