import os
import subprocess

def converter_audio(input_path, output_path):
    """
    Recebe o caminho de um arquivo de áudio qualquer (input_path)
    e converte para um WAV configurado corretamente (output_path).
    Retorna True se der certo, False se der erro.
    """
    
    # Define onde está o ffmpeg (assumindo pasta 'ffmpeg' na raiz do projeto)
    ffmpeg_path = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")

    if not os.path.exists(ffmpeg_path):
        print(f"[ERRO] ffmpeg não encontrado em: {ffmpeg_path}")
        return False

    print(f"[CONVERSOR] Iniciando: '{input_path}' -> '{output_path}'")

    comando = [
        ffmpeg_path,
        "-y",            # Sobrescrever arquivo de saída se existir
        "-i", input_path,
        "-vn",           # Ignorar vídeo (caso o usuário mande MP4)
        "-acodec", "pcm_s16le", # Codec de áudio padrão para WAV
        "-ar", "16000",  # Taxa de amostragem ideal para IA (Whisper)
        "-ac", "1",      # Mono (1 canal) é melhor para reconhecimento de fala
        output_path
    ]

    try:
        # Executa o comando escondendo a saída bagunçada do FFMPEG
        subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        print("[CONVERSOR] Sucesso!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERRO CONVERSAO] O FFMPEG falhou. Código: {e.returncode}")
        return False
    except Exception as e:
        print(f"[ERRO GERAL] {e}")
        return False