# Meu Treino

App em Streamlit para registrar o treino na academia: peso e repetições de cada série.
Ele mostra o que você fez da última vez naquele exercício e grava tudo numa planilha
do Google, então o histórico não se perde ao trocar de celular ou limpar o navegador.

## O que o app faz

- Abre no treino do dia, com as mesmas séries, pesos e reps da última vez que você fez cada exercício.
- Todos os exercícios começam abertos. Quando todas as séries de um exercício estão gravadas, ele fecha e ganha ✅; toque nele para reabrir.
- Depois de digitar a senha, o app não pede de novo por 4 horas sem uso, mesmo que o celular apague a tela ou você troque de app. Para mudar o tempo, use `horas_sessao` nos secrets.
- 💾 grava a série. Depois disso o botão vira ✅ e fica travado; se você mudar o peso ou as reps, ele volta a 💾 para gravar a correção.
- 🗑️ exclui uma série (se ela já estiver gravada, pede confirmação e renumera as seguintes). **＋ Série** adiciona uma série.
- ⏱️ cronômetro de descanso desde a última série gravada.
- 💡 avisa para subir a carga quando, no último treino, você bateu o topo da meta de reps em todas as séries.
- 🏆 avisa quando você grava a maior carga que já fez no exercício.
- **＋ Incluir exercício neste treino** (no fim da aba Treino): escolha região > músculo > exercício. Ele pode ficar fixo no plano do dia ou entrar só hoje.
- ▶️ **Como fazer**: toca o vídeo de exemplo do exercício. Se ainda não tiver vídeo, o botão *Procurar no YouTube* abre a busca pronta; cole o link do vídeo que gostar (Shorts funciona) e ele fica salvo para as próximas vezes.
- Aba **Montar treino**: para cada dia da semana, adicione exercícios pela lista de músculos, mude séries e meta, reordene (⬆️⬇️) ou tire (🗑️). Tirar um exercício não apaga o histórico dele. Se o exercício não estiver na lista, escolha *Outro* e digite o nome.
- Aba **Histórico**: treinos realizados, evolução de carga por exercício, download de tudo em CSV e importação do backup do app antigo.

## Alunos

Cada pessoa tem o próprio treino e histórico. No topo do app, escolha o aluno em **👤 Aluno**, ou
**＋ Novo aluno** para criar um. O aluno padrão é Fabrício Lopes. Um aluno novo começa sem treino:
ele monta o dele na aba *Montar treino* ou copia o de outro aluno e ajusta.
A lista de exercícios e os vídeos são compartilhados entre todos.

## Como os dados ficam na planilha

Os treinos ficam na **mesma planilha do bazar**, em abas próprias. As abas `itens` e `vendas` não são tocadas.

- **Treino <nome do aluno>** (ex.: `Treino Fabrício Lopes`, `Treino Anah`): o histórico daquele aluno, uma aba por aluno.
  Na primeira vez, a aba vazia `Página1` vira `Treino Fabrício Lopes`. Se a `Página1` tiver algum conteúdo, ela
  é mantida e o app cria uma aba nova. A aba de um aluno novo é criada quando ele é criado no app.
  Cada série concluída vira uma linha:
  `data | dia_treino | exercicio | serie | peso_kg | reps | hora | registrado_em | intervalo_seg`
  Se você corrigir uma série, a mesma linha é atualizada e o horário original é mantido.
- **treinos_academia_plano**: os exercícios de cada dia, de todos os alunos (coluna `aluno`). O app cria essa aba
  sozinho com o plano atual do Fabrício, e ela é atualizada pela aba *Montar treino*.
  Se editar direto na planilha, toque em 🔄 no app depois. Na meta de reps, escreva `8–12` ou `8 a 12`,
  porque `8-12` com hífen comum o Google transforma em data.
- **treinos_academia_exercicios**: os exercícios criados com *Outro* e os links de vídeo de cada exercício.

A lista de músculos e exercícios fica em `catalogo.py`. O histórico é ligado ao nome do exercício, então
não renomeie um exercício que já tem treinos gravados.

Como a conta de serviço do bazar já é editora dessa planilha, não é preciso compartilhar nada.

## Passo 1: secrets

Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha:

- `planilha_id`: o mesmo do app do bazar.
- `senha_app`: uma senha sua. O link do Streamlit é público, então sem senha qualquer pessoa com o link veria e editaria seus treinos.
- `horas_sessao` (opcional, padrão 4): por quantas horas sem uso o app fica liberado depois de digitar a senha.
- `[gcp_service_account]`: copie o bloco inteiro do `secrets.toml` do app do bazar.

Esse arquivo **nunca vai para o GitHub** (já está no `.gitignore`).

## Passo 2: testar no computador

Com uma planilha falsa em memória, sem tocar na planilha real:

```powershell
$env:TREINO_MODO_TESTE = "1"; streamlit run app.py
```

Com a planilha real: `streamlit run app.py`

## Passo 3: publicar

1. O código está no GitHub: https://github.com/fabricio-atua/app-treino-academia
2. Em https://share.streamlit.io, entre com a conta GitHub **fabricio-atua**, clique em **Create app** >
   **Deploy a public app from GitHub**, escolha o repositório `fabricio-atua/app-treino-academia`,
   branch `main` e arquivo `app.py`.
3. Em **Advanced settings > Secrets**, cole o conteúdo do seu `secrets.toml` e clique em **Deploy**.

## Passo 4: ícone no celular

Cada aluno salva o próprio link, com o nome dele e a senha, para o app abrir direto no treino certo:
`https://SEU-APP.streamlit.app/?aluno=Fabrício Lopes&chave=SUA_SENHA`

O jeito mais fácil: abra o app, digite a senha, escolha o aluno no topo e só então adicione à tela inicial.
O endereço já fica com `?aluno=...`. Para não pedir a senha, acrescente `&chave=SUA_SENHA` no fim do endereço antes.

- **Android (Chrome):** menu ⋮ > **Adicionar à tela inicial**.
- **iPhone (Safari):** botão Compartilhar > **Adicionar à Tela de Início**.

## Trazer os treinos do app antigo (HTML)

No app antigo, toque em **Exportar backup**. No app novo, vá na aba **Histórico > Importar backup do app antigo**
e envie o arquivo `.json`. Séries que já estão na planilha não são duplicadas.

## Bom saber

- Depois de um tempo sem uso, o Streamlit Cloud "adormece" o app. Na primeira abertura aparece um botão
  para acordá-lo, e isso leva uns 30 segundos.
- O intervalo entre séries é o tempo entre um salvamento e o seguinte: inclui o descanso e a execução da série.
