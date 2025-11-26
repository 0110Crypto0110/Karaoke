import os
import subprocess

def converter_e_renomear(pasta="audios"):
    pasta_abs = os.path.join(os.getcwd(), pasta)

    ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg","ffmpeg.exe")

    if not os.path.exists(ffmpeg_path):
        print("[ERRO] ffmpeg.exe não encontrado em ffmpeg/bin/")
        print("Coloque o FFmpeg dentro da pasta do projeto:")
        print("Karaoke-main/ffmpeg/bin/ffmpeg.exe")
        return

    arquivos = os.listdir(pasta_abs)
    if not arquivos:
        print("[AVISO] Nenhum arquivo encontrado na pasta de áudio.")
        return

    for arquivo in arquivos:
        caminho = os.path.join(pasta_abs, arquivo)

        # ignora pastas
        if not os.path.isfile(caminho):
            continue

        destino = os.path.join(pasta_abs, "canto.wav")

        print(f"[INFO] Convertendo '{arquivo}' → canto.wav")

        # comando ffmpeg: converte qualquer formato para wav
        comando = [
            ffmpeg_path,
            "-y",            # sobrescrever sem perguntar
            "-i", caminho,   # entrada
            destino          # saída
        ]

        try:
            subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("[OK] Conversão concluída.")
        except Exception as e:
            print("[ERRO] Falha ao converter:", e)

        return  # Para no primeiro arquivo válido encontrado

    print("[AVISO] Nenhum arquivo de áudio válido encontrado.")

if __name__ == "__main__":
    converter_e_renomear()
