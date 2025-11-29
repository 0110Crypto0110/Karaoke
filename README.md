refiz a estrutura, ajeitei um pasta e reduzi a quantidade de arquivos;

refiz um dart unico(para usarmos a funcao de gravar audio no app precisamos de uma permissao no android, 
oloquei ela abaixo no arquivo, na pasta lib, junto do main dart)

(tambem precisa definir corretamente o ip no arquivo dart_main o: SERVER_URL, para funcionar).


concertei o fluxo do e modularidedade dos arquivos python
(agora script usa letras_csv para buscar
as letras das musicas )

(se rodar script sozinho ele vai buscar uma musica especifica em hardcoded "the search", 
tambem tem o audio dela cantando para testar)

(por fim defini melhor o servidor.py; se implementado corretamente ele espera do dart o audio,
 os dados da musica e os passam para letras e script)

(tentei gerar um dart generico, ainda nao sei para onde vai,
teoricamente ele tem um espaço pro video do karaoke,
uma parte para enviar o audio, e outra para o relatorio do desenpenho.
)
