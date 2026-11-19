# Jarvis Local

Assistente de voz que roda **no meu PC**, sem API paga. Aperto **F8**, falo um comando e ele abre o programa, o site ou o jogo, e responde falando.

> **Projeto criado com ajuda de IA (Claude).** Eu defini os requisitos, escrevi os prompts, configurei os módulos (por exemplo, troquei a integração do Spotify), ajustei a lista de apelidos e testei o resultado.

## O que ele faz

- Abre programas, sites e jogos da Steam por comando de voz: "Abra o navegador", "Abra o YouTube", "Abra a Steam", "Abra o WhatsApp".
- Responde com voz em português do Brasil e fala as horas.
- Mostra uma janela com uma esfera animada que muda conforme o estado: ouvindo, pensando, falando.
- Roda localmente: reconhecimento de voz, IA e voz sintetizada ficam no computador.

## Como funciona

| Parte | Tecnologia |
|---|---|
| Interpretar o que eu falo | [Whisper](https://github.com/SYSTRAN/faster-whisper) (faster-whisper) |
| Entender o pedido | Modelo `qwen3.5:9b`, rodando pelo [Ollama](https://ollama.com) |
| Falar | [Piper](https://github.com/rhasspy/piper), voz `pt_BR-faber-medium` |
| Janela | Tkinter |
| Tecla de ativação | biblioteca `keyboard` (F8) |

## Um problema real que resolvi

O Whisper erra nomes de aplicativos: "Gmail" vira "jimeio", "WhatsApp" vira "uatsapp". Fiz uma lista de apelidos para cada programa (no dicionário `APPS`) e o Jarvis reconhece os erros mais comuns. Novos programas e sites podem ser adicionados no arquivo `meus_apps.json`, sem mexer no código.

## Requisitos

- **Windows** (usa o registro do Windows e o Menu Iniciar)
- **Placa de vídeo NVIDIA** com CUDA
- Python 3.10 ou mais novo
- [Ollama](https://ollama.com) instalado

## Como rodar

```bash
# 1. Instalar as dependências
pip install -r requirements.txt

# 2. Baixar o modelo de IA
ollama pull qwen3.5:9b

# 3. Baixar a voz Piper (pt_BR-faber-medium.onnx e o .json) e colocar na pasta do projeto
#    https://huggingface.co/rhasspy/piper-voices

# 4. Rodar
python app.py
```

Aperte **F8** para chamar o Jarvis.

## Configuração

No topo do `app.py`: modelo, tecla, tempo de espera da fala e sensibilidade do microfone.

## Limitações

- Só funciona no Windows com placa NVIDIA.
- Reconhece apenas os programas da lista `APPS` e do `meus_apps.json`.
- Projeto pessoal, feito para aprender.
