from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import sys

# Importando seus módulos personalizados
# Certifique-se de que script.py, letras_csv.py e audio_converter.py estão na mesma pasta
try:
    import script
    import letras_csv
    import audio_converter
except ImportError as e:
    print(f"[ERRO DE IMPORTAÇÃO] Falha ao importar módulos: {e}")
    print("Verifique se script.py, letras_csv.py e audio_converter.py estão na pasta.")
    sys.exit(1)

app = Flask(__name__)
CORS(app) # Habilita CORS para o App Flutter conseguir acessar

# --- CONFIGURAÇÕES ---
PASTA_AUDIOS = "audios"
ARQUIVO_CSV = "musicas.csv"

# Cria a pasta de áudios se não existir
os.makedirs(PASTA_AUDIOS, exist_ok=True)

# --- CARREGAMENTO DOS MODELOS (GLOBAL) ---
# Isso acontece apenas UMA vez quando o servidor liga.
print("\n" + "="*50)
print("[SERVIDOR] Inicializando e carregando modelos de IA...")
print("[SERVIDOR] Isso pode levar alguns segundos...")
script.configurar_ffmpeg_local()
stt_model, sim_model = script.load_models()
print("[SERVIDOR] Modelos carregados! Pronto para receber requisições.")
print("="*50 + "\n")

@app.route('/analisar', methods=['POST'])
def analisar_karaoke():
    """
    Rota principal. O App Dart envia:
    - audio (arquivo)
    - titulo (texto)
    - artista (texto)
    """
    caminho_temp = None
    caminho_wav = None

    try:
        # 1. VALIDAÇÃO DOS DADOS RECEBIDOS
        titulo = request.form.get('titulo')
        artista = request.form.get('artista')
        
        if 'audio' not in request.files:
            return jsonify({"erro": "Nenhum arquivo de áudio enviado"}), 400
        
        arquivo = request.files['audio']
        
        if not titulo or not artista:
            return jsonify({"erro": "Campos 'titulo' e 'artista' são obrigatórios"}), 400

        print(f"\n[REQ] Nova análise solicitada: {titulo} - {artista}")

        # 2. SALVAR O ÁUDIO TEMPORÁRIO
        # Gera um nome aleatório para não misturar arquivos de usuários diferentes
        nome_unico = f"upload_{uuid.uuid4().hex}"
        extensao_orig = os.path.splitext(arquivo.filename)[1]
        if not extensao_orig: extensao_orig = ".m4a" # fallback padrão

        caminho_temp = os.path.join(PASTA_AUDIOS, nome_unico + extensao_orig)
        caminho_wav = os.path.join(PASTA_AUDIOS, nome_unico + ".wav")
        
        arquivo.save(caminho_temp)
        print(f"[ARQUIVO] Salvo temporariamente em: {caminho_temp}")

        # 3. CONVERTER ÁUDIO (Chamada Automática ao audio_converter)
        sucesso_conversao = audio_converter.converter_audio(caminho_temp, caminho_wav)
        
        # Se a conversão falhar, abortamos
        if not sucesso_conversao:
            return jsonify({"erro": "O servidor falhou ao converter o formato do áudio."}), 500

        # 4. BUSCAR A LETRA (Local ou Online)
        # Tenta carregar do CSV
        palavras_original = None
        try:
            df = script.carregar_csv_palavras(ARQUIVO_CSV)
            palavras_original = script.montar_letra_por_palavras(df, titulo)
        except Exception:
            pass # Se der erro ao ler CSV, assumimos que precisa buscar

        # Se não achou no CSV, busca online e salva
        if palavras_original is None:
            print(f"[LETRA] Não encontrada localmente. Buscando '{titulo}' online...")
            encontrou = letras_csv.buscar_e_adicionar_letra(titulo, artista, ARQUIVO_CSV)
            
            if encontrou:
                # Recarrega o CSV atualizado
                df = script.carregar_csv_palavras(ARQUIVO_CSV)
                palavras_original = script.montar_letra_por_palavras(df, titulo)
            else:
                return jsonify({"erro": "Não encontramos a letra dessa música."}), 404

        # 5. EXECUTAR ANÁLISE (Script Principal)
        print("[IA] Transcrevendo áudio...")
        texto_usuario = script.transcrever_audio(stt_model, caminho_wav)
        palavras_usuario = texto_usuario.split()

        print("[IA] Alinhando e comparando...")
        palavras_alinh_o, palavras_alinh_u = script.alinhar_inteligente(sim_model, palavras_original, palavras_usuario)
        media_sim, scores = script.comparar_palavras(sim_model, palavras_alinh_o, palavras_alinh_u)
        nota_final = script.calcular_nota(media_sim)
        info_faltantes = script.detectar_palavras_faltantes(palavras_original, palavras_usuario)

        # 6. FORMATAR RESPOSTA JSON
        # Prepara a lista detalhada para o App pintar as palavras de verde/vermelho
        detalhes = []
        for o, u, s in zip(palavras_alinh_o, palavras_alinh_u, scores):
            # Classificação simples para o front-end
            status = "ruim"
            if s > 0.85: status = "otimo"
            elif s > 0.60: status = "bom"
            
            detalhes.append({
                "original": o,
                "usuario": u,
                "score": float(f"{s:.4f}"),
                "status": status
            })

        resposta = {
            "sucesso": True,
            "musica": titulo,
            "artista": artista,
            "nota_final": nota_final,
            "similaridade_media": float(f"{media_sim:.4f}"),
            "cobertura_letra": info_faltantes["cobertura"],
            "palavras_nao_cantadas": info_faltantes["faltantes"],
            "analise_detalhada": detalhes
        }

        print(f"[SUCESSO] Análise concluída. Nota: {nota_final}/99")
        return jsonify(resposta)

    except Exception as e:
        print(f"[ERRO CRÍTICO] {e}")
        return jsonify({"erro": f"Erro interno no servidor: {str(e)}"}), 500
    
    finally:
        # 7. LIMPEZA (Sempre executa, mesmo se der erro)
        # Remove os arquivos de áudio para não lotar o servidor
        if caminho_temp and os.path.exists(caminho_temp):
            os.remove(caminho_temp)
        if caminho_wav and os.path.exists(caminho_wav):
            os.remove(caminho_wav)

if __name__ == "__main__":
    # Rodar o servidor
    # host='0.0.0.0' permite acesso via rede local (WiFi)
    print("[INIT] Servidor Flask rodando na porta 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)