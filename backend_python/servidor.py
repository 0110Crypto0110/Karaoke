from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import sys

# === CONFIGURAÇÃO DE CAMINHOS ABSOLUTOS ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))       
ROOT_DIR = os.path.dirname(BASE_DIR)                        

PASTA_AUDIOS = os.path.join(ROOT_DIR, "audios")
ARQUIVO_CSV = os.path.join(ROOT_DIR, "musicas.csv")

# Importando seus módulos personalizados
try:
    import script
    import letras_csv
    import audio_converter
except ImportError as e:
    print(f"[ERRO DE IMPORTAÇÃO] Falha ao importar módulos: {e}")
    print("Verifique se script.py, letras_csv.py e audio_converter.py estão na pasta.")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

# Cria a pasta audios se não existir
os.makedirs(PASTA_AUDIOS, exist_ok=True)

# --- CARREGAMENTO GLOBAL ---
print("\n" + "="*50)
print("[SERVIDOR] Inicializando e carregando modelos de IA...")
script.configurar_ffmpeg_local()
stt_model, sim_model = script.load_models()
print("[SERVIDOR] Modelos carregados!")
print("="*50 + "\n")


@app.route('/analisar', methods=['POST'])
def analisar_karaoke():

    caminho_temp = None
    caminho_wav = None

    try:
        titulo = request.form.get('titulo')
        artista = request.form.get('artista')

        if 'audio' not in request.files:
            return jsonify({"erro": "Nenhum arquivo de áudio enviado"}), 400

        arquivo = request.files['audio']

        if not titulo or not artista:
            return jsonify({"erro": "Campos 'titulo' e 'artista' são obrigatórios"}), 400

        print(f"\n[REQ] Nova análise solicitada: {titulo} - {artista}")

        # Criando nome temporário
        nome_unico = f"upload_{uuid.uuid4().hex}"
        extensao_orig = os.path.splitext(arquivo.filename)[1] or ".m4a"

        caminho_temp = os.path.join(PASTA_AUDIOS, nome_unico + extensao_orig)
        caminho_wav = os.path.join(PASTA_AUDIOS, nome_unico + ".wav")

        arquivo.save(caminho_temp)
        print(f"[ARQUIVO] Salvo temporariamente em: {caminho_temp}")

        # Conversão
        sucesso_conversao = audio_converter.converter_audio(caminho_temp, caminho_wav)
        if not sucesso_conversao:
            return jsonify({"erro": "Erro ao converter áudio"}), 500

        # Carregar letra do CSV
        try:
            df = script.carregar_csv_palavras(ARQUIVO_CSV)
            palavras_original = script.montar_letra_por_palavras(df, titulo)
        except:
            palavras_original = None

        # Busca online se não existir no CSV
        if palavras_original is None:
            encontrou = letras_csv.buscar_e_adicionar_letra(titulo, artista, ARQUIVO_CSV)
            if not encontrou:
                return jsonify({"erro": "Letra não encontrada"}), 404

            df = script.carregar_csv_palavras(ARQUIVO_CSV)
            palavras_original = script.montar_letra_por_palavras(df, titulo)

        # Análises
        texto_usuario = script.transcrever_audio(stt_model, caminho_wav)
        palavras_usuario = texto_usuario.split()

        palavras_alinh_o, palavras_alinh_u = script.alinhar_inteligente(
            sim_model, palavras_original, palavras_usuario
        )

        media_sim, scores = script.comparar_palavras(
            sim_model, palavras_alinh_o, palavras_alinh_u
        )

        nota_final = script.calcular_nota(media_sim)
        info_faltantes = script.detectar_palavras_faltantes(
            palavras_original, palavras_usuario
        )

        # Resposta detalhada
        detalhes = []
        for o, u, s in zip(palavras_alinh_o, palavras_alinh_u, scores):
            status = "ruim"
            if s > 0.85: status = "otimo"
            elif s > 0.60: status = "bom"

            detalhes.append({
                "original": o,
                "usuario": u,
                "score": float(f"{s:.4f}"),
                "status": status
            })

        return jsonify({
            "sucesso": True,
            "musica": titulo,
            "artista": artista,
            "nota_final": nota_final,
            "similaridade_media": float(f"{media_sim:.4f}"),
            "cobertura_letra": info_faltantes["cobertura"],
            "palavras_nao_cantadas": info_faltantes["faltantes"],
            "analise_detalhada": detalhes
        })

    except Exception as e:
        print(f"[ERRO CRÍTICO] {e}")
        return jsonify({"erro": str(e)}), 500

    finally:
        if caminho_temp and os.path.exists(caminho_temp):
            os.remove(caminho_temp)
        if caminho_wav and os.path.exists(caminho_wav):
            os.remove(caminho_wav)


if __name__ == "__main__":
    print("[INIT] Servidor rodando na porta 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)
