import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:youtube_player_flutter/youtube_player_flutter.dart';
import 'package:record/record.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

// --- CONFIGURAÇÕES DO SERVIDOR E MÚSICA ---
// IMPORTANTE: Use o IP da sua máquina, não 'localhost' (127.0.0.1)
// se estiver usando um emulador/dispositivo físico.
const String SERVER_URL = 'http://192.168.1.100:5000/analisar'; 
const String YOUTUBE_VIDEO_ID = 'y8yA4nUoGgY'; // Exemplo: The Search - NF
const String MUSICA_TITULO = 'The Search';
const String MUSICA_ARTISTA = 'NF';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Karaoke Analyzer',
      theme: ThemeData(
        primarySwatch: Colors.blueGrey,
        useMaterial3: true,
      ),
      home: const KaraokeScreen(),
    );
  }
}

// --- MODELO DE DADOS PARA RECEBER DO PYTHON (JSON) ---
class PerformanceData {
  final int notaFinal;
  final double similaridadeMedia;
  final List<dynamic> analiseDetalhada;

  PerformanceData({
    required this.notaFinal,
    required this.similaridadeMedia,
    required this.analiseDetalhada,
  });

  factory PerformanceData.fromJson(Map<String, dynamic> json) {
    return PerformanceData(
      notaFinal: json['nota_final'] as int? ?? 0,
      similaridadeMedia: json['similaridade_media'] as double? ?? 0.0,
      analiseDetalhada: json['analise_detalhada'] as List<dynamic>? ?? [],
    );
  }
}

// --- TELA PRINCIPAL ---
class KaraokeScreen extends StatefulWidget {
  const KaraokeScreen({super.key});

  @override
  State<KaraokeScreen> createState() => _KaraokeScreenState();
}

class _KaraokeScreenState extends State<KaraokeScreen> {
  late YoutubePlayerController _controller;
  final audioRecorder = AudioRecorder();
  String? _audioPath;
  bool _isRecording = false;
  bool _isLoading = false;
  PerformanceData? _performanceData;

  @override
  void initState() {
    super.initState();
    _controller = YoutubePlayerController(
      initialVideoId: YOUTUBE_VIDEO_ID,
      flags: const YoutubePlayerFlags(
        autoPlay: false,
        mute: false,
        disableDragControls: true,
        loop: false,
        isLive: false,
        forceHD: true,
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    audioRecorder.dispose();
    super.dispose();
  }

  // --- 🎤 FUNÇÕES DE GRAVAÇÃO ---
  Future<void> _startRecording() async {
    try {
      if (await audioRecorder.hasPermission()) {
        final dir = await getApplicationDocumentsDirectory();
        _audioPath = '${dir.path}/karaoke_user_audio.m4a';

        await audioRecorder.start(
          const RecordConfig(encoder: AudioEncoder.m4a),
          path: _audioPath!,
        );

        _controller.seekTo(const Duration(seconds: 0));
        _controller.play();

        setState(() {
          _isRecording = true;
          _performanceData = null; // Limpa resultados antigos
        });
      }
    } catch (e) {
      print('Erro ao iniciar gravação: $e');
      // Exibir Snackbar de erro
    }
  }

  Future<void> _stopRecording() async {
    try {
      final path = await audioRecorder.stop();
      _controller.pause();
      setState(() {
        _isRecording = false;
        _audioPath = path;
      });
      if (path != null) {
        _sendForAnalysis(path);
      }
    } catch (e) {
      print('Erro ao parar gravação: $e');
    }
  }

  // --- 🚀 FUNÇÃO DE ENVIO PARA O SERVIDOR PYTHON ---
  Future<void> _sendForAnalysis(String audioFilePath) async {
    setState(() {
      _isLoading = true;
    });

    try {
      var request = http.MultipartRequest('POST', Uri.parse(SERVER_URL));
      
      // Adiciona campos de texto para o servidor Python
      request.fields['titulo'] = MUSICA_TITULO;
      request.fields['artista'] = MUSICA_ARTISTA;

      // Adiciona o arquivo de áudio
      request.files.add(await http.MultipartFile.fromPath(
        'audio',
        audioFilePath,
      ));

      var response = await request.send();
      
      if (response.statusCode == 200) {
        var responseData = await response.stream.bytesToString();
        var jsonResponse = jsonDecode(responseData);
        
        setState(() {
          _performanceData = PerformanceData.fromJson(jsonResponse);
        });
      } else {
        var errorBody = await response.stream.bytesToString();
        print('Erro no servidor (${response.statusCode}): $errorBody');
        // Mostrar erro para o usuário
        _showErrorDialog('Erro de Servidor', 'Status: ${response.statusCode}. Verifique o console do Python.');
      }
    } catch (e) {
      print('Erro de conexão: $e');
      _showErrorDialog('Erro de Conexão', 'Não foi possível conectar ao servidor Python. Verifique o IP e a porta.');
    } finally {
      setState(() {
        _isLoading = false;
      });
      // Deleta o arquivo temporário após o upload
      if (await File(audioFilePath).exists()) {
        await File(audioFilePath).delete();
      }
    }
  }

  // --- WIDGETS DE DISPLAY ---
  void _showErrorDialog(String title, String content) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(content),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Widget _buildResultDisplay() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_performanceData == null) {
      return const Center(child: Text('Grave seu áudio para iniciar a análise.'));
    }

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 🏆 NOTA FINAL
          Card(
            color: Colors.lightGreen.shade100,
            margin: const EdgeInsets.all(8.0),
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  const Text('Nota Final:', style: TextStyle(fontSize: 18)),
                  Text(
                    '${_performanceData!.notaFinal}/99',
                    style: const TextStyle(
                      fontSize: 48, 
                      fontWeight: FontWeight.bold, 
                      color: Colors.lightGreen
                    ),
                  ),
                  Text('Similaridade Média: ${_performanceData!.similaridadeMedia.toStringAsFixed(3)}'),
                ],
              ),
            ),
          ),

          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
            child: Text('Análise Detalhada (Original <> Cantado):', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
          // 📝 ANÁLISE DETALHADA (LISTA DE PALAVRAS)
          ..._performanceData!.analiseDetalhada.map((item) {
            String original = item['original'] ?? '';
            String usuario = item['usuario'] ?? '';
            double score = item['score'] as double? ?? 0.0;
            String status = item['status'] ?? 'ruim';
            
            Color color;
            switch (status) {
              case 'otimo': color = Colors.green.shade100; break;
              case 'bom': color = Colors.amber.shade100; break;
              default: color = Colors.red.shade100; break;
            }

            return Card(
              color: color,
              margin: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
              child: ListTile(
                title: Text(original, style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text(usuario.isNotEmpty ? usuario : '[Não Cantada/Ignorada]'),
                trailing: Text('Score: ${score.toStringAsFixed(3)}'),
              ),
            );
          }).toList(),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Karaoke IA'),
        backgroundColor: Theme.of(context).primaryColor,
      ),
      body: Column(
        children: <Widget>[
          // 📺 PLAYER DE VÍDEO
          YoutubePlayer(
            controller: _controller,
            showVideoProgressIndicator: true,
            progressIndicatorColor: Colors.blueAccent,
            onReady: () {
              print('Player está pronto.');
            },
          ),
          
          const SizedBox(height: 10),

          // 🔴 BOTÃO DE GRAVAÇÃO/PARADA
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ElevatedButton.icon(
                  onPressed: _isRecording ? _stopRecording : _startRecording,
                  icon: Icon(_isRecording ? Icons.stop : Icons.mic),
                  label: Text(_isRecording ? 'Parar Gravação' : 'Gravar Karaokê'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isRecording ? Colors.red : Colors.blueGrey,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 15),
                  ),
                ),
              ],
            ),
          ),
          
          const SizedBox(height: 10),
          
          // --- RESULTADOS ---
          Expanded(
            child: _buildResultDisplay(),
          ),
        ],
      ),
    );
  }
}