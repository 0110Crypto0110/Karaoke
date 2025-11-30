import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:youtube_player_flutter/youtube_player_flutter.dart';
import 'package:record/record.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

const String SERVER_URL = 'http://192.168.1.100:5000/analisar';
const String YOUTUBE_VIDEO_ID = 'y8yA4nUoGgY';
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

// ======================================================
//       MODELO DE RESPOSTA DO SERVIDOR PYTHON
// ======================================================
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
      notaFinal: json['nota_final'] ?? 0,
      similaridadeMedia: (json['similaridade_media'] ?? 0).toDouble(),
      analiseDetalhada: json['analise_detalhada'] ?? [],
    );
  }
}

// ======================================================
//                   TELA PRINCIPAL
// ======================================================
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

  // ======================================================
  //            INICIAR GRAVAÇÃO
  // ======================================================
  Future<void> _startRecording() async {
    try {
      final hasPermission = await audioRecorder.hasPermission();

      if (!hasPermission) {
        _showErrorDialog(
          'Permissão necessária',
          'O aplicativo precisa de acesso ao microfone.',
        );
        return;
      }

      final dir = await getApplicationDocumentsDirectory();
      _audioPath = '${dir.path}/karaoke_user_audio.m4a';

      await audioRecorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 128000,
          sampleRate: 44100,
        ),
        path: _audioPath!,
      );

      _controller.seekTo(Duration.zero);
      _controller.play();

      setState(() {
        _isRecording = true;
        _performanceData = null;
      });
    } catch (e) {
      _showErrorDialog('Erro ao gravar', e.toString());
    }
  }

  // ======================================================
  //             PARAR GRAVAÇÃO
  // ======================================================
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
      _showErrorDialog('Erro ao parar gravação', e.toString());
    }
  }

  // ======================================================
  //        ENVIO DO ÁUDIO PARA O SERVIDOR PYTHON
  // ======================================================
  Future<void> _sendForAnalysis(String audioFilePath) async {
    setState(() {
      _isLoading = true;
    });

    try {
      final request = http.MultipartRequest('POST', Uri.parse(SERVER_URL));

      request.fields['titulo'] = MUSICA_TITULO;
      request.fields['artista'] = MUSICA_ARTISTA;

      request.files.add(
        await http.MultipartFile.fromPath('audio', audioFilePath),
      );

      final response = await request.send();

      if (response.statusCode == 200) {
        final responseData = await response.stream.bytesToString();
        final jsonResponse = jsonDecode(responseData);

        setState(() {
          _performanceData = PerformanceData.fromJson(jsonResponse);
        });
      } else {
        _showErrorDialog(
          'Erro no servidor',
          'Status ${response.statusCode}',
        );
      }
    } catch (e) {
      _showErrorDialog('Erro de conexão', e.toString());
    } finally {
      setState(() {
        _isLoading = false;
      });

      if (await File(audioFilePath).exists()) {
        await File(audioFilePath).delete();
      }
    }
  }

  // ======================================================
  //               EXIBIR ERRO
  // ======================================================
  void _showErrorDialog(String title, String content) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(content),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  // ======================================================
  //                  EXIBIÇÃO DOS RESULTADOS
  // ======================================================
  Widget _buildResultDisplay() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_performanceData == null) {
      return const Center(
        child: Text('Grave seu áudio para iniciar a análise.'),
      );
    }

    return SingleChildScrollView(
      child: Column(
        children: [
          Card(
            color: Colors.lightGreen.shade100,
            margin: const EdgeInsets.all(8),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  const Text('Nota Final:', style: TextStyle(fontSize: 18)),
                  Text(
                    '${_performanceData!.notaFinal}/99',
                    style: const TextStyle(
                      fontSize: 42,
                      fontWeight: FontWeight.bold,
                      color: Colors.green,
                    ),
                  ),
                  Text(
                    'Similaridade Média: ${_performanceData!.similaridadeMedia.toStringAsFixed(3)}',
                  ),
                ],
              ),
            ),
          ),

          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text(
              'Análise Detalhada:',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),

          ..._performanceData!.analiseDetalhada.map((item) {
            final original = item['original'] ?? '';
            final usuario = item['usuario'] ?? '';
            final score = item['score'] ?? 0.0;
            final status = item['status'] ?? 'ruim';

            Color color = Colors.red.shade100;
            if (status == 'bom') color = Colors.amber.shade100;
            if (status == 'otimo') color = Colors.green.shade100;

            return Card(
              color: color,
              child: ListTile(
                title: Text(original),
                subtitle: Text(
                  usuario.isEmpty ? '[Não cantada]' : usuario,
                ),
                trailing: Text('Score: ${score.toStringAsFixed(3)}'),
              ),
            );
          }).toList(),
        ],
      ),
    );
  }

  // ======================================================
  //                   INTERFACE
  // ======================================================
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Karaoke IA'),
        backgroundColor: Theme.of(context).primaryColor,
      ),
      body: Column(
        children: [
          YoutubePlayer(
            controller: _controller,
            showVideoProgressIndicator: true,
          ),

          const SizedBox(height: 10),

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

          const SizedBox(height: 10),

          Expanded(child: _buildResultDisplay()),
        ],
      ),
    );
  }
}
