# letra_csv.py
import csv
import re
import os

def gerar_csv_palavras(titulo, artista, letra, arquivo_csv="musicas.csv"):
    palavras = re.findall(r"\b\w+'\w+|\w+\b", letra)

    with open(arquivo_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "titulo", "artista", "palavra"])

        for idx, palavra in enumerate(palavras, 1):
            writer.writerow([idx, titulo, artista, palavra])

    print(f"[OK] CSV gerado em: {os.path.abspath(arquivo_csv)}")


if __name__ == "__main__":
    print("Digite o título da música:")
    titulo = input("> ").strip()

    print("Digite o artista:")
    artista = input("> ").strip()

    print("Cole a letra inteira da música abaixo e pressione ENTER duas vezes:")
    linhas = []
    while True:
        linha = input()
        if linha.strip() == "":
            break
        linhas.append(linha)

    letra = "\n".join(linhas)

    gerar_csv_palavras(titulo, artista, letra)
