# Studio Nave

Uma sala de operações em pixel art para ver, em tempo real, o que seus agentes do Claude Code estão fazendo.

- Cada **módulo** da nave é uma sessão do Claude Code (um projeto aberto).
- O **comandante** no centro é a sessão principal.
- A **tripulação** nas estações são os subagentes (Explore, Plan, ou os seus, como `pesquisador`).
- O **Painel** mostra quantas execuções estão trabalhando, delegando, aguardando, concluídas ou sem sinal.

Funciona no Mac e no Windows e não precisa instalar nada além do Python.

## Como funciona

```text
Claude Code --hooks--> ~/.studionave/events.jsonl --> studionave.py (servidor local) --> navegador
```

O Claude Code chama um pequeno script (`hooks/capture.py`) sempre que uma sessão ou subagente começa ou termina. Esse script grava **somente metadados** (identificadores, tipo do agente, pasta do projeto, horário). Ele nunca grava seus prompts, respostas ou conversas. Tudo fica no seu computador; o servidor só escuta em `127.0.0.1`.

## Passo a passo

### 1. Tenha o Python instalado

Abra o terminal (Mac: app **Terminal**; Windows: app **PowerShell**) e cole:

```bash
python3 --version
```

No Windows, use `py --version`. Se aparecer `Python 3.10` ou maior, está pronto. Se não, baixe em [python.org/downloads](https://www.python.org/downloads/) (no Windows, marque a opção **Add Python to PATH** na instalação).

> Nos comandos abaixo, no Windows troque `python3` por `py`.

### 2. Baixe este repositório

```bash
cd ~
git clone https://github.com/izzasimoes-sketch/studionave.git
cd studionave
```

### 3. Veja a demonstração (opcional)

```bash
python3 studionave.py demo
```

O navegador abre sozinho com dados de exemplo. Para fechar, volte ao terminal e aperte `Ctrl+C`.

### 4. Conecte ao Claude Code

```bash
python3 studionave.py instalar
```

Isso adiciona os hooks em `~/.claude/settings.json` (uma cópia de segurança é salva como `settings.json.studionave-backup`). Seus outros hooks e configurações não são alterados.

### 5. Abra a sala

```bash
python3 studionave.py iniciar
```

Deixe esse terminal aberto. Agora abra **uma nova sessão** do Claude Code em qualquer projeto: ela aparece na sala em poucos segundos.

## Comandos

| Comando | O que faz |
| --- | --- |
| `python3 studionave.py iniciar` | Abre a sala com seus dados reais |
| `python3 studionave.py demo` | Abre a sala com dados de exemplo (separados dos reais) |
| `python3 studionave.py instalar` | Registra os hooks no Claude Code |
| `python3 studionave.py remover` | Remove só os hooks do Studio Nave |

Opções: `--porta 8877` para usar outra porta e `--sem-navegador` para não abrir o navegador sozinho.

Importante: não mude a pasta do repositório de lugar depois de instalar. Se precisar, rode `remover`, mova a pasta e rode `instalar` de novo.

## Estados

| Estado | Significado |
| --- | --- |
| Trabalhando | Recebeu um pedido e está executando |
| Delegando | A sessão principal passou trabalho para subagentes |
| Aguardando | Terminou e espera sua próxima mensagem |
| Concluída | Sessão encerrada ou subagente terminou |
| Sem sinal | A sessão parou sem avisar (por exemplo, o terminal foi fechado) |

## Limites

- Só aparecem sessões do Claude Code que rodam **no seu computador**. Sessões na nuvem (claude.ai/code) não chegam até a sala.
- A página atualiza a cada 4 segundos.
- Mostra as últimas 24 horas; sessões concluídas ficam na sala por 12 horas.

## Testes

```bash
python3 -m unittest discover -s tests
```

## Créditos

Inspirado no [AI Operations Room](https://github.com/mewsdev/AiOperationsRoom) (MIT) e no [Pixel Agents](https://github.com/pixel-agents-hq/pixel-agents). Todo o código e a arte deste projeto foram escritos do zero.

Licença MIT.
