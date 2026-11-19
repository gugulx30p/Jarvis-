import os, re, json, time, queue, threading, unicodedata, difflib, webbrowser, traceback
import subprocess, shutil, atexit
import collections, random, math
import urllib.parse
from datetime import datetime
import numpy as np
import nvidia.cublas, nvidia.cudnn
for m in (nvidia.cublas, nvidia.cudnn):
    pasta = os.path.join(list(m.__path__)[0], "bin")
    os.add_dll_directory(pasta)
    os.environ["PATH"] = pasta + os.pathsep + os.environ["PATH"]

try:  # deixa a janela nítida em telas com zoom
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
try:
    from PIL import Image
except ImportError:
    Image = None
import sounddevice as sd
import ollama
from faster_whisper import WhisperModel
from piper import PiperVoice

try:
    import keyboard
except ImportError:
    keyboard = None

# ---------------- CONFIGURAÇÃO ----------------
MODELO = "qwen3.5:9b"
ARQUIVO_VOZ = "pt_BR-faber-medium.onnx"
DICA = ("Jarvis, abra a Steam, Spotify, Chrome, Claude, ChatGPT, Gmail, YouTube, Google, "
        "WhatsApp, Teams, FC 26, FxSound, painel de controle, gerenciador de tarefas, volume, "
        "que horas são.")

MODO = "f8"               # "f8" = tecla + janela | "enter" = modo antigo no terminal
TECLA = "f8"              # tecla que chama o Jarvis
ESPERA_FALA = 6           # segundos esperando você começar a falar (depois a janela fecha)
LIMIAR_MINIMO = 0.010     # volume mínimo para considerar que você está falando
SILENCIO_FIM = 1.5        # segundos de silêncio para saber que você terminou (mais = não corta)
MAX_FALA = 30             # segundos máximos de uma fala
ARQUIVO_APPS = "meus_apps.json"
ARQUIVO_IMAGEM = "jarvis.png"          # esfera animada (opcional; sem ela usa a esfera desenhada)
ARQUIVO_FUNDO = "jarvis_fundo.png"     # fundo da janela (opcional)
IMG_TAM = 280                          # tamanho da esfera na janela
FUNDO_ESCURO = 0.34                    # 0 = preto, 1 = fundo no brilho original
# mudança de cor da esfera por estado (graus de matiz, em unidades de 0 a 255)
DESLOC_COR = {"ouvindo": -14, "pensando": 42, "falando": -43, "erro": 99}
VEL_GIRO = {"ouvindo": 7, "pensando": 70, "falando": 22, "erro": 3}   # graus por segundo
KEEP_ALIVE_MODELO = "5m"  # tempo que o modelo fica na placa de vídeo depois do último uso
OLLAMA_OCIOSO_MIN = 8     # minutos parado até o Jarvis DESLIGAR o servidor do Ollama
                          # (só desliga se foi o próprio Jarvis que ligou)
SAUDACOES = ["Pois não, senhor?", "O que precisa, senhor?", "Às ordens, senhor.",
             "Em que posso ajudar, senhor?"]

SISTEMA = (
    "Você é o Jarvis, assistente pessoal por voz do usuário, a quem você chama de "
    "senhor. Seu jeito é caloroso, simpático e comunicativo, com um toque de "
    "mordomo elegante e bom humor leve. Fale português do Brasil. "
    "Responda em até três frases curtas. "
    "Não use markdown, listas, emojis nem símbolos, pois sua resposta será falada."
)

# Só muda o ÁUDIO. A tela mostra a grafia correta.
PRONUNCIA = {
    "Steam": "Estim",
    "Spotify": "Espotifai",
    "Corinthians": "Coríntians",
    "YouTube": "Iutiube",
    "UFC": "U efe cê",
    "Claude": "Clód",
    "Gmail": "Jimeio",
    "ChatGPT": "Chéti gê pê tê",
    "FC": "éfe cê",
    "WhatsApp": "Uótsape",
}

# Programas permitidos: nome: (o que o Windows abre, apelidos que o Whisper pode escrever)
# Para adicionar sites/programas SEM mexer aqui, use o arquivo meus_apps.json
APPS = {
    "steam": ("steam://open/main",
              ["steam", "estim", "estinga", "stim", "esteam", "istim"]),
    "navegador": ("https://www.google.com",
                  ["navegador", "chrome", "browser", "google"]),
    "gmail": ("https://mail.google.com",
              ["gmail", "email", "emails", "mail", "jimeio", "gmeio"]),
    "youtube": ("https://www.youtube.com",
                ["youtube", "iutiube", "utube", "iutube"]),
    "Spotify": (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Spotify.lnk"),
            ["spotfast", "spotifast", "spotfaste", "spotify", "espotifai",
             "spotifai", "espotify", "musica"]),
    "teams": ("msteams:", ["teams", "tims"]),
    "whatsapp": ("whatsapp:", ["whatsapp", "whatsap", "uatsapp", "uotsapp", "zap",
                               "zapzap", "wpp", "watsapp"]),
    "calculadora": ("calc.exe", ["calculadora"]),
    "claude": ("https://claude.ai", ["claude", "cloud", "clode"]),
    "chatgpt": ("https://chatgpt.com", ["chatgpt", "gpt", "gepete"]),
    "gerenciador de tarefas": ("taskmgr", ["gerenciador", "tarefas", "taskmgr"]),
    "explorador": ("explorer", ["explorador", "arquivos", "explorer"]),
    "bloco de notas": ("notepad", ["bloco", "notas", "notepad"]),
    "configurações": ("ms-settings:", ["configuracoes", "configuracao", "ajustes"]),
    "painel de controle": ("control", ["painel", "control"]),
    "gerenciador de dispositivos": ("devmgmt.msc", ["dispositivos", "devmgmt"]),
}

# Verbos FORTES: sempre significam "abrir" e também começam um novo pedido na frase
VERBOS_FORTES = ["abrir", "abre", "abra", "abri", "iniciar", "inicia", "inicie",
                 "ligar", "liga", "coloca", "coloque", "mostra", "mostre",
                 "puxe", "puxa", "traga", "traz", "execute", "executa", "rode"]
# Verbos FRACOS: só valem em frases curtas (evita abrir coisa sem querer)
VERBOS_FRACOS = ["quero", "preciso", "vamos", "bora", "entra", "entre", "ver",
                 "veja", "joga", "jogar", "toca", "tocar", "leva", "va", "vai", "ir"]
VERBOS_PESQUISA = ["pesquise", "pesquisa", "pesquisar", "busque", "buscar", "procure",
                   "procura", "procurar"]
MAX_PALAVRAS_FRACO = 6

SEPARADORES = {"depois", "seguida", "tambem", "finalmente"}
SITES_YOUTUBE = {"youtube", "iutiube", "utube", "iutube"}
SITES_PALAVRAS = SITES_YOUTUBE | {"google", "internet", "navegador"}
IGNORAR_INICIO = {"no", "na", "pelo", "pela", "por", "sobre", "para", "pra", "a", "o",
                  "os", "as", "um", "uma", "me", "ai", "isso", "que", "de", "com",
                  "falando", "assunto", "tema", "algo", "coisa", "e", "la", "fale"}
IGNORAR_FIM = {"no", "na", "em", "pelo", "pela", "do", "da", "de", "e", "la", "com"}
# Palavras que NÃO fazem parte do nome de um jogo/programa
SOBRA_NOME = IGNORAR_INICIO | {"jogo", "jogos", "jogar", "game", "ok", "jarvis", "entao",
                               "favor", "pode", "voce", "poderia", "novamente", "ja",
                               "tambem", "ainda", "agora", "mas", "se", "puder",
                               "programa", "aplicativo", "app"}
DESPEDIDAS = {"tchau", "obrigado", "obrigada", "dispensado", "valeu"}

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

FERRAMENTAS_PLANO = ["abrir_app", "abrir_programa", "pesquisar", "abrir_jogo", "listar_jogos"]
ESQUEMA_PLANO = {
    "type": "object",
    "properties": {
        "acoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ferramenta": {"type": "string", "enum": FERRAMENTAS_PLANO},
                    "alvo": {"type": "string"},
                    "site": {"type": "string", "enum": ["google", "youtube"]},
                },
                "required": ["ferramenta", "alvo"],
            },
        },
        "resposta": {"type": "string"},
    },
    "required": ["acoes", "resposta"],
}
# ----------------------------------------------

nivel_mic = 0.0   # volume atual do microfone (a esfera reage a ele)
ui = None         # janela (só existe no modo f8)


def ui_enviar(*msg):
    if ui is not None:
        ui.enviar(*msg)


# ---------------- JANELA (esfera) ----------------
FUNDO = "#0a0f1e"
TRANSP = "#010203"        # cor "invisível" do Windows (faz os cantos arredondados)
LARG, ALT = 440, 640
CORES = {"ouvindo": "#22d3ee", "pensando": "#a78bfa", "falando": "#34d399",
         "erro": "#fb7185"}
ROTULOS = {"ouvindo": "OUVINDO", "pensando": "PENSANDO", "falando": "FALANDO",
           "erro": "ERRO"}


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def preparar_orbes(caminho, d):
    """Esfera por estado: fundo preto vira transparente (brilho 'soma' com o fundo) e a cor muda."""
    from PIL import Image
    base = Image.open(caminho).convert("RGB").resize((d, d), Image.LANCZOS)
    hsv = np.asarray(base.convert("HSV")).astype(int)
    saidas = {}
    for estado, desloc in DESLOC_COR.items():
        canais = [Image.fromarray((((hsv[..., 0] + desloc) % 256)).astype("uint8")),
                  Image.fromarray(hsv[..., 1].astype("uint8")),
                  Image.fromarray(hsv[..., 2].astype("uint8"))]
        rgb = np.asarray(Image.merge("HSV", canais).convert("RGB")).astype(float)
        rgb = np.clip((rgb - 0.07 * 255) / 0.93, 0, 255)          # o "preto" da imagem vira preto de verdade
        a0 = np.clip(rgb.max(axis=2) / 255.0 * 1.25, 0, 1)
        cor = np.clip(rgb / np.maximum(a0[..., None], 1 / 255.0), 0, 255)
        yy, xx = np.mgrid[0:d, 0:d]
        raio = np.hypot(xx - (d - 1) / 2, yy - (d - 1) / 2) / (d / 2)
        a = a0 * np.clip((1.0 - raio) / 0.12, 0, 1)                # borda some suavemente (sem quadrado)
        saidas[estado] = Image.fromarray(np.dstack([cor, a * 255]).astype("uint8"))
    return saidas


def preparar_fundo(caminho, w, h, raio):
    """Recorta o fundo no formato da janela, escurece (mais embaixo, onde fica o texto) e arredonda."""
    from PIL import Image, ImageDraw
    im = Image.open(caminho).convert("RGB")
    cw = int(im.height * w / h)
    im = im.crop((0, 0, min(cw, im.width), im.height)).resize((w, h), Image.LANCZOS)
    arr = np.asarray(im).astype(float) * FUNDO_ESCURO
    arr = np.clip(arr * np.linspace(1.0, 0.45, h)[:, None, None], 0, 255)
    out = Image.fromarray(arr.astype("uint8")).convert("RGBA")
    mascara = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=raio * 3, fill=255)
    out.putalpha(mascara.resize((w, h), Image.LANCZOS))
    return out


def misturar(a, b, t):
    """Mistura duas cores RGB. t=0 devolve a, t=1 devolve b."""
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


class Interface:
    def __init__(self):
        self.msgs = queue.Queue()
        self.estado = "ouvindo"
        self.rotulo_extra = ""
        self.blocos = []          # [("Você", texto), ("Jarvis", texto)]
        self.rev = 0              # quantas letras da fala do Jarvis já apareceram
        self.visivel = False
        self.alpha = 0.0
        self.alpha_alvo = 0.0
        self.arrasto = None
        self.hover_x = False
        self.amp = 0.0
        self.cor = list(_rgb(CORES["ouvindo"]))

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            pass
        try:
            self.root.attributes("-transparentcolor", TRANSP)   # cantos arredondados
        except Exception:
            pass
        self.root.configure(bg=TRANSP)

        self.E = min(3.0, max(1.0, self.root.winfo_fpixels("1i") / 96.0))  # zoom da tela
        E = self.E
        self.orbes, self.img, self.ang, self.img_fundo = self._carregar_orbes(), None, 0.0, None
        self.W, self.H = int(LARG * E), int(ALT * E)
        x = self.root.winfo_screenwidth() - self.W - int(40 * E)
        y = self.root.winfo_screenheight() - self.H - int(80 * E)
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg=TRANSP,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.card = self._rr(3, 3, LARG - 3, ALT - 3, 30, fill=FUNDO,
                             outline="#1c2a4a", width=max(2, int(2 * E)))

        self._criar_fundo()
        self.canvas.bind("<ButtonPress-1>", self._clique)
        self.canvas.bind("<B1-Motion>", self._arrastar)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "arrasto", None))
        self.canvas.bind("<Motion>", self._mover)

        self.t0 = time.time()
        self.root.after(33, self.animar)
        self.root.after(50, self.ler_fila)

    # ---------- desenho ----------
    def _carregar_orbes(self):
        """Carrega jarvis.png (esfera animada). Sem Pillow ou sem arquivo: devolve None."""
        try:
            if not os.path.exists(ARQUIVO_IMAGEM):
                return None
            from PIL import ImageTk
            self._ImageTk = ImageTk
            orbes = preparar_orbes(ARQUIVO_IMAGEM, int(IMG_TAM * self.E))
            print(f"[esfera {ARQUIVO_IMAGEM} carregada]")
            return orbes
        except Exception as e:
            print(f"[esfera do Jarvis não carregada ({e}); usando a esfera desenhada]")
            return None

    def _criar_fundo(self):
        try:
            if not os.path.exists(ARQUIVO_FUNDO):
                return
            from PIL import ImageTk
            E = self.E
            im = preparar_fundo(ARQUIVO_FUNDO, int((LARG - 6) * E), int((ALT - 6) * E), 28)
            self.img_fundo = ImageTk.PhotoImage(im)
            self.canvas.create_image(3 * E, 3 * E, image=self.img_fundo, anchor="nw", tags="fundo")
            print(f"[fundo {ARQUIVO_FUNDO} carregado]")
        except Exception as e:
            print(f"[fundo não carregado ({e})]")

    def _rr(self, x1, y1, x2, y2, r, **kw):
        """Retângulo com cantos arredondados."""
        E = self.E
        x1, y1, x2, y2, r = x1 * E, y1 * E, x2 * E, y2 * E, r * E
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _o(self, cx, cy, r, **kw):
        E = self.E
        kw.setdefault("tags", "dyn")
        return self.canvas.create_oval((cx - r) * E, (cy - r) * E,
                                       (cx + r) * E, (cy + r) * E, **kw)

    def _no_x(self, e):
        E = self.E
        return abs(e.x - (LARG - 34) * E) < 16 * E and abs(e.y - 34 * E) < 16 * E

    def _clique(self, e):
        if self._no_x(e):
            self.alpha_alvo = 0.0          # só esconde a janela
            return
        self.arrasto = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _arrastar(self, e):
        if self.arrasto:
            self.root.geometry(f"+{e.x_root - self.arrasto[0]}+{e.y_root - self.arrasto[1]}")

    def _mover(self, e):
        self.hover_x = self._no_x(e)

    # ---------- mensagens vindas do resto do programa ----------
    def enviar(self, *msg):
        self.msgs.put(msg)

    def _definir_texto(self, s):
        blocos = []
        for parte in s.split("\n\n"):
            parte = parte.strip()
            if not parte:
                continue
            if ":" in parte[:8]:
                quem, _, txt = parte.partition(":")
                if quem.strip() in ("Você", "Jarvis"):
                    blocos.append((quem.strip(), txt.strip()))
                    continue
            blocos.append(("Jarvis", parte))
        novo = next((t for q, t in blocos if q == "Jarvis"), "")
        antigo = next((t for q, t in self.blocos if q == "Jarvis"), "")
        if novo != antigo:
            self.rev = 0                   # recomeça o efeito de digitação
        self.blocos = blocos

    def ler_fila(self):
        try:
            while True:
                m = self.msgs.get_nowait()
                if m[0] == "mostrar":
                    if not self.visivel:
                        self.alpha = 0.0
                        try:
                            self.root.attributes("-alpha", 0.0)
                        except Exception:
                            pass
                    self.root.deiconify()
                    self.root.attributes("-topmost", True)
                    self.root.lift()
                    self.visivel = True
                    self.alpha_alvo = 0.97
                elif m[0] == "esconder":
                    self.alpha_alvo = 0.0          # esmaece e some
                elif m[0] == "estado":
                    self.estado = m[1]
                    self.rotulo_extra = ""
                elif m[0] == "rotulo":
                    self.rotulo_extra = m[1]
                elif m[0] == "texto":
                    self._definir_texto(m[1])
        except queue.Empty:
            pass
        self.root.after(50, self.ler_fila)

    # ---------- animação ----------
    def animar(self):
        c, E = self.canvas, self.E
        t = time.time() - self.t0

        # esmaecer (entrar e sair)
        self.alpha += (self.alpha_alvo - self.alpha) * 0.25
        if abs(self.alpha_alvo - self.alpha) < 0.01:
            self.alpha = self.alpha_alvo
        try:
            self.root.attributes("-alpha", max(0.0, min(1.0, self.alpha)))
        except Exception:
            pass
        if self.visivel and self.alpha_alvo == 0.0 and self.alpha == 0.0:
            self.root.withdraw()
            self.visivel = False
        if not self.visivel:
            self.root.after(100, self.animar)      # escondida: quase não gasta nada
            return

        bg = _rgb(FUNDO)
        alvo = _rgb(CORES.get(self.estado, "#22d3ee"))
        self.cor = [self.cor[i] + (alvo[i] - self.cor[i]) * 0.12 for i in range(3)]
        cor = tuple(self.cor)

        if self.estado == "ouvindo":
            alvo_amp = min(nivel_mic * 25, 1.0)
        elif self.estado == "falando":
            alvo_amp = 0.5 + 0.3 * abs(math.sin(t * 7)) * (0.6 + 0.4 * math.sin(t * 2.3))
        elif self.estado == "pensando":
            alvo_amp = 0.25 + 0.08 * math.sin(t * 3)
        else:
            alvo_amp = 0.15
        self.amp += (alvo_amp - self.amp) * 0.3
        amp = self.amp

        c.delete("dyn")
        c.itemconfig(self.card, outline=_hex(misturar(bg, cor, 0.45)))

        cx, cy, base = LARG / 2, 172, 46

        # brilho ao redor (círculos que escurecem para fora)
        brilho = (0.55 + 0.45 * amp) * (0.45 if self.orbes else 1.0)
        for i in range(12, 0, -1):
            r = base + i * 6.5 + amp * 10
            k = (1 - i / 13.0) ** 2.2 * 0.55 * brilho
            self._o(cx, cy, r, fill=_hex(misturar(bg, cor, k)), outline="")

        # ondas que se expandem
        for k in range(3):
            fase = (t * 0.55 + k / 3.0) % 1.0
            r = base + 8 + fase * 70 * (0.5 + amp)
            self._o(cx, cy, r, outline=_hex(misturar(bg, cor, (1 - fase) * 0.6 * (0.5 if self.orbes else 1.0))),
                    width=max(1, int(2 * E)))

        # esfera com degradê (centro claro, borda escura)
        r0 = base + amp * 7 + 2 * math.sin(t * 2)
        if self.orbes:
            self.ang = (self.ang + VEL_GIRO.get(self.estado, 7) * 0.033 * (1 + amp * 2)) % 360
            base_im = self.orbes.get(self.estado) or self.orbes["ouvindo"]
            quadro = base_im.rotate(self.ang, resample=Image.BILINEAR)
            esc = 1.0 + amp * 0.10
            if esc > 1.01:
                lado = int(base_im.width * esc)
                quadro = quadro.resize((lado, lado), Image.BILINEAR)
            self.img = self._ImageTk.PhotoImage(quadro)
            c.create_image(cx * E, cy * E, image=self.img, tags="dyn")
        else:
            passos = 16
            for i in range(passos):
                f = i / (passos - 1)
                r = r0 * (1 - f * 0.82)
                claro = misturar(misturar(bg, cor, 0.55), (255, 255, 255), f ** 1.6 * 0.75)
                self._o(cx - f * r0 * 0.22, cy - f * r0 * 0.25, r,
                        fill=_hex(claro), outline="")
            self._o(cx, cy, r0, outline=_hex(misturar(bg, cor, 0.9)), width=max(1, int(2 * E)))

        # pensando: arcos e bolinhas girando
        if self.estado == "pensando":
            R = base + 34
            for k in range(3):
                c.create_arc((cx - R) * E, (cy - R) * E, (cx + R) * E, (cy + R) * E,
                             start=(t * 150 + k * 120) % 360, extent=55, style="arc",
                             outline=_hex(misturar(cor, (255, 255, 255), 0.6)),
                             width=max(2, int(3 * E)), tags="dyn")
            for k in range(6):
                a = t * 2.2 + k * math.pi / 3
                self._o(cx + math.cos(a) * (base + 54), cy + math.sin(a) * (base + 54), 3,
                        fill=_hex(misturar(cor, (255, 255, 255), 0.5)), outline="")

        # barrinhas de som
        n, larg_b, gap, wy = 31, 5, 4, 352
        total = n * (larg_b + gap) - gap
        x0 = cx - total / 2
        for i in range(n):
            d = abs(i - (n - 1) / 2) / ((n - 1) / 2)
            if self.estado == "ouvindo":
                h = 3 + amp * 34 * (1 - d * 0.75) * (0.6 + 0.4 * abs(math.sin(t * 9 + i * 0.8)))
            elif self.estado == "falando":
                h = 3 + amp * 30 * (1 - d * 0.6) * (0.5 + 0.5 * abs(math.sin(t * 8 + i * 0.6)))
            elif self.estado == "pensando":
                h = 3 + 9 * (0.5 + 0.5 * math.sin(t * 4 - i * 0.5))
            else:
                h = 3
            xb = x0 + i * (larg_b + gap)
            c.create_rectangle(xb * E, (wy - h / 2) * E, (xb + larg_b) * E,
                               (wy + h / 2) * E, outline="", tags="dyn",
                               fill=_hex(misturar(bg, cor, 0.35 + 0.55 * (1 - d))))

        # título, botão de fechar, estado e dica
        self._o(36, 34, 4, fill=_hex(cor), outline="")
        c.create_text(50 * E, 34 * E, text="J A R V I S", anchor="w", fill="#cfe6ff",
                      font=("Segoe UI Semibold", 11), tags="dyn")
        c.create_text((LARG - 34) * E, 34 * E, text="✕", fill="#ff8a9b" if self.hover_x else "#5b6b88",
                      font=("Segoe UI", 12), tags="dyn")
        if self.rotulo_extra:
            rot = self.rotulo_extra
        else:
            rot = " ".join(ROTULOS.get(self.estado, ""))
        c.create_text(cx * E, 318 * E, text=rot, fill=_hex(misturar(cor, (255, 255, 255), 0.35)),
                      font=("Segoe UI Semibold", 10), tags="dyn")
        c.create_line(30 * E, 392 * E, (LARG - 30) * E, 392 * E,
                      fill=_hex(misturar(bg, cor, 0.2)), tags="dyn")
        c.create_text(cx * E, (ALT - 26) * E, text="F8 chama  ·  diga “tchau” para fechar",
                      fill="#4b5b78", font=("Segoe UI", 9), tags="dyn")

        # conversa (a fala do Jarvis aparece letra por letra)
        jarvis_len = sum(len(tx) for q, tx in self.blocos if q == "Jarvis")
        if self.rev < jarvis_len:
            self.rev += 3
        self._desenhar_texto(cor)

        self.root.after(33, self.animar)

    def _desenhar_texto(self, cor):
        c, E = self.canvas, self.E
        visiveis = [(q, tx[:self.rev] if q == "Jarvis" else tx) for q, tx in self.blocos]
        y1 = ALT - 52
        for _ in range(8):
            c.delete("txt")
            y = 410
            for quem, tx in visiveis:
                if quem == "Jarvis" and not tx:
                    continue
                cor_l = _hex(cor) if quem == "Jarvis" else "#6e82a5"
                c.create_text(30 * E, y * E, text=quem.upper(), anchor="nw", fill=cor_l,
                              font=("Segoe UI Semibold", 8), tags=("dyn", "txt"))
                y += 17
                item = c.create_text(30 * E, y * E, text=tx, anchor="nw", fill="#e6eefc",
                                     font=("Segoe UI", 11), width=(LARG - 60) * E,
                                     tags=("dyn", "txt"))
                bb = c.bbox(item)
                y = (bb[3] / E + 12) if bb else y + 20
            if y - 12 <= y1:
                break
            # não coube: tira o começo do texto mais antigo
            if len(visiveis) > 1:
                visiveis.pop(0)
            else:
                q, tx = visiveis[0]
                visiveis[0] = (q, "…" + tx[len(tx) // 4:])


# ---------------- TEXTO ----------------
def data_hora_texto():
    agora = datetime.now()
    return (f"Data de hoje: {DIAS[agora.weekday()]}, {agora.day} de "
            f"{MESES[agora.month - 1]} de {agora.year}. Hora atual: {agora:%H:%M}.")


def sistema_plano():
    return (SISTEMA + " " + data_hora_texto() + "\n"
            "Você responde SOMENTE em JSON com os campos 'acoes' e 'resposta'.\n"
            "- 'acoes': lista, NA ORDEM PEDIDA, de coisas a fazer no computador. "
            "Vazia se o usuário só quer conversar ou perguntar algo.\n"
            "  * abrir_app: alvo = um destes programas: " + ", ".join(APPS) + ".\n"
            "  * abrir_programa: alvo = nome de qualquer outro programa instalado.\n"
            "  * abrir_jogo: alvo = nome de um jogo da Steam.\n"
            "  * pesquisar: alvo = assunto da pesquisa, site = google ou youtube. "
            "Uma ação para cada pesquisa pedida.\n"
            "  * listar_jogos: alvo vazio, para dizer quais jogos estão instalados.\n"
            "Entenda a intenção mesmo sem a palavra 'abrir' ('quero ver meu e-mail' = "
            "abrir gmail; 'bora jogar UFC' = abrir_jogo).\n"
            "- 'resposta': se 'acoes' estiver vazia, sua resposta falada (até três "
            "frases curtas, sem símbolos). Se houver ações, uma frase curta. "
            "Só diga que não sabe quando a pergunta exigir informação atual, como "
            "notícias, clima ou placar. Traduções e conversa comum você responde.")


def limpar_titulo(t):
    return re.sub(r"[™®©]", "", t).replace("  ", " ").strip()


def para_fala(texto):
    texto = limpar_titulo(texto)
    for palavra, fala in PRONUNCIA.items():
        texto = re.sub(rf"\b{palavra}\b", fala, texto, flags=re.IGNORECASE)
    return texto


def normalizar(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", texto).split()


def parecido(palavra, lista, corte=0.8):
    return bool(difflib.get_close_matches(palavra, lista, n=1, cutoff=corte))


def carregar_meus_apps():
    """Lê o arquivo meus_apps.json (você edita no Bloco de Notas). Cria um exemplo se não existir."""
    if not os.path.exists(ARQUIVO_APPS):
        exemplo = {"exemplo (apague ou edite)": {
            "abrir": "https://www.netflix.com", "apelidos": ["netflix", "netflics"]}}
        with open(ARQUIVO_APPS, "w", encoding="utf-8") as f:
            json.dump(exemplo, f, ensure_ascii=False, indent=2)
        return
    try:
        with open(ARQUIVO_APPS, encoding="utf-8") as f:
            dados = json.load(f)
        for nome, d in dados.items():
            if nome.lower().startswith("exemplo"):
                continue
            apelidos = []
            for ap in d.get("apelidos", []) + [nome]:
                apelidos.extend(normalizar(ap))
            APPS[nome.lower()] = (os.path.expandvars(d["abrir"]), apelidos)
            print(f"[meus_apps: {nome} carregado]")
    except Exception as e:
        print(f"[aviso: não consegui ler {ARQUIVO_APPS}: {e}]")


def achar_apps(texto):
    """Todos os programas citados na frase (sem repetir). 'navegador' só vale sozinho."""
    achados = []
    for p in normalizar(texto):
        for nome, (_, apelidos) in APPS.items():
            if (p == nome or parecido(p, apelidos, 0.85)) and nome not in achados:
                achados.append(nome)
    if len(achados) > 1 and "navegador" in achados:
        achados.remove("navegador")
    return achados


def achar_app(texto):
    achados = achar_apps(texto)
    return achados[0] if achados else None


# ---------------- ABRIR COISAS NO WINDOWS ----------------
def trazer_para_frente():
    """Libera o Windows para o programa aberto aparecer NA FRENTE (e não por trás)."""
    try:
        import ctypes
        u = ctypes.windll.user32
        u.AllowSetForegroundWindow(ctypes.c_uint(0xFFFFFFFF))
        u.keybd_event(0x12, 0, 0, 0)
        u.keybd_event(0x12, 0, 2, 0)
    except Exception as e:
        print(f"[aviso: não consegui liberar o foco: {e}]")


ALTERNATIVAS = {"whatsapp:": "https://web.whatsapp.com"}   # se o app não estiver instalado


def protocolo_instalado(alvo):
    """True se o Windows tem um programa registrado para esse tipo de endereço (ex.: whatsapp:)."""
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, alvo.rstrip(":")))
        return True
    except OSError:
        return False


def executar(alvo):
    """Abre um site, programa ou atalho. Mostra no terminal o que aconteceu."""
    trazer_para_frente()
    if alvo in ALTERNATIVAS and not protocolo_instalado(alvo):
        print(f"[abrir: {alvo} não está instalado; usando {ALTERNATIVAS[alvo]}]")
        alvo = ALTERNATIVAS[alvo]
    try:
        os.startfile(alvo)
        print(f"[abrir: startfile ok -> {alvo}]")
    except Exception:
        print(f"[abrir: startfile FALHOU para {alvo}]")
        traceback.print_exc()
        if alvo.startswith("http"):
            print(f"[webbrowser.open_new_tab -> {webbrowser.open_new_tab(alvo)}]")
        else:
            raise


def url_pesquisa(consulta, site):
    q = urllib.parse.quote_plus(consulta)
    if site == "youtube":
        return f"https://www.youtube.com/results?search_query={q}"
    return f"https://www.google.com/search?q={q}"


# ---------------- STEAM ----------------
def pasta_steam():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return winreg.QueryValueEx(k, "SteamPath")[0].replace("/", "\\")
    except Exception:
        return r"C:\Program Files (x86)\Steam"


def pastas_biblioteca():
    base = pasta_steam()
    pastas = [os.path.join(base, "steamapps")]
    vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, encoding="utf-8", errors="ignore") as f:
            for p in re.findall(r'"path"\s+"(.+?)"', f.read()):
                pastas.append(os.path.join(p.replace("\\\\", "\\"), "steamapps"))
    except Exception:
        pass
    vistos, final = set(), []
    for p in pastas:
        if p.lower() not in vistos and os.path.isdir(p):
            vistos.add(p.lower())
            final.append(p)
    return final


IGNORAR_JOGOS = ("steamworks", "proton", "steam linux runtime", "redistributable")


def jogos_instalados():
    jogos = []
    for pasta in pastas_biblioteca():
        try:
            arquivos = os.listdir(pasta)
        except Exception:
            continue
        for arq in arquivos:
            if arq.startswith("appmanifest_") and arq.endswith(".acf"):
                try:
                    with open(os.path.join(pasta, arq), encoding="utf-8",
                              errors="ignore") as f:
                        txt = f.read()
                    appid = re.search(r'"appid"\s+"(\d+)"', txt).group(1)
                    nome = re.search(r'"name"\s+"(.+?)"', txt).group(1)
                except Exception:
                    continue
                if not any(x in nome.lower() for x in IGNORAR_JOGOS):
                    jogos.append((appid, nome))
    return jogos


def achar_jogo(consulta, minimo=0.6):
    """Acha o jogo instalado mais parecido. 'FC26' casa com 'EA SPORTS FC 26'."""
    q = normalizar(consulta)
    qc = "".join(q)
    melhor, melhor_nota = None, 0.0
    for appid, nome in jogos_instalados():
        gt = normalizar(nome)
        if not q or not gt:
            continue
        gc = "".join(gt)
        cobertura = sum(1 for t in q if t in gt or parecido(t, gt)) / len(q)
        ratio = difflib.SequenceMatcher(None, " ".join(q), " ".join(gt)).ratio()
        nota = max(ratio, cobertura * 0.95)
        if len(qc) >= 3 and qc in gc:
            nota = max(nota, 0.9 + min(len(qc) / len(gc), 1) * 0.05)
        if nota > melhor_nota:
            melhor, melhor_nota = (appid, nome), nota
    return melhor if melhor_nota >= minimo else None


# ---------------- ATALHOS DO MENU INICIAR (lista guardada ao iniciar) ----------------
_ATALHOS = []


def carregar_atalhos():
    global _ATALHOS
    pastas = [os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
              os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs")]
    lista = []
    for pasta in pastas:
        for raiz, _, arquivos in os.walk(pasta):
            for a in arquivos:
                if a.lower().endswith(".lnk"):
                    n = " ".join(normalizar(a[:-4]))
                    if "uninstall" in n or "desinstal" in n:
                        continue
                    lista.append((n, os.path.join(raiz, a)))
    _ATALHOS = lista


def achar_atalho(consulta, minimo=0.7):
    q = " ".join(normalizar(consulta))
    melhor, melhor_nota = None, 0.0
    for n, caminho in _ATALHOS:
        nota = difflib.SequenceMatcher(None, q, n).ratio()
        if len(q) >= 3 and q in n:
            nota = max(nota, 0.95)
        if nota > melhor_nota:
            melhor, melhor_nota = caminho, nota
    return melhor if melhor_nota >= minimo else None


# ---------------- AÇÕES (executadas pelo CÓDIGO, nunca pelo modelo) ----------------
def abrir_app(nome):
    chave = achar_app(nome)
    if not chave:
        return f"erro: programa '{nome}' não está na lista"
    executar(APPS[chave][0])
    return f"ok: {chave} aberto"


def abrir_programa(nome):
    atalho = achar_atalho(nome)
    if not atalho:
        return f"erro: não achei o programa '{nome}' no Menu Iniciar"
    executar(atalho)
    return f"ok: {os.path.basename(atalho)[:-4]} aberto"


def pesquisar(consulta, site="google"):
    site = (site or "google").lower().strip()
    executar(url_pesquisa(consulta, site))
    return f"ok: pesquisando {consulta} no {site}"


def abrir_jogo(nome):
    achado = achar_jogo(nome)
    if not achado:
        nomes = [limpar_titulo(n) for _, n in jogos_instalados()]
        lista = ", ".join(nomes[:15]) if nomes else "nenhum jogo encontrado"
        return f"erro: jogo '{nome}' não encontrado. Instalados: {lista}"
    appid, titulo = achado
    executar(f"steam://rungameid/{appid}")
    return f"ok: abrindo {limpar_titulo(titulo)}"


def listar_jogos():
    nomes = sorted(limpar_titulo(n) for _, n in jogos_instalados())
    return "ok: jogos instalados: " + (", ".join(nomes[:25]) if nomes else "nenhum")


def executar_acao(ferramenta, alvo, site="google"):
    try:
        if ferramenta == "abrir_app":
            r = abrir_app(alvo)
            if r.startswith("erro"):
                r = abrir_programa(alvo)
            return r
        if ferramenta == "abrir_programa":
            return abrir_programa(alvo)
        if ferramenta == "pesquisar":
            return pesquisar(alvo, site)
        if ferramenta == "abrir_jogo":
            return abrir_jogo(alvo)
        if ferramenta == "listar_jogos":
            return listar_jogos()
        return f"erro: ação desconhecida '{ferramenta}'"
    except Exception as e:
        traceback.print_exc()
        return f"erro: {e}"


def executar_lista(acoes, nao_entendi=None):
    """Executa as ações em ordem e devolve a frase falada com o que REALMENTE aconteceu."""
    oks, erros = [], []
    for i, (ferramenta, alvo, site) in enumerate(acoes):
        if i > 0:
            time.sleep(0.5)
        resultado = executar_acao(ferramenta, alvo, site)
        print(f"[ação {ferramenta}({alvo!r}, {site!r}) -> {resultado}]")
        if resultado.startswith("ok: "):
            oks.append(resultado[4:])
        else:
            erros.append(resultado.replace("erro: ", "", 1))
    partes = []
    if oks:
        lista = ", ".join(oks[:-1]) + " e " + oks[-1] if len(oks) > 1 else oks[0]
        partes.append(f"Pronto, senhor: {lista}.")
    if erros:
        partes.append("Mas tive um problema: " + "; ".join(erros) + ".")
    for trecho in (nao_entendi or []):
        partes.append(f"Não entendi esta parte: {trecho}.")
    return " ".join(partes) if partes else "Não consegui fazer isso, senhor."


# ---------------- CAMADA 0 (sem modelo) ----------------
def dividir_em_pedidos(palavras):
    """Divide a frase em pedidos separados: a cada verbo forte e a cada 'depois'."""
    pedidos, atual = [], []
    for p in palavras:
        if p in SEPARADORES:
            if atual:
                pedidos.append(atual)
            atual = []
        elif p in VERBOS_FORTES:
            if atual and any(t in VERBOS_FORTES for t in atual):
                pedidos.append(atual)
                atual = []
            atual.append(p)
        else:
            atual.append(p)
    if atual:
        pedidos.append(atual)
    return pedidos


def acoes_do_pedido(cl, herda_verbo=False):
    """Devolve (lista de ações, pedido_tinha_intenção_mas_não_foi_entendido)."""
    if not cl:
        return [], False
    tem_forte_proprio = any(parecido(t, VERBOS_FORTES) for t in cl)
    tem_forte = tem_forte_proprio or herda_verbo   # "depois o gerenciador": herda o "abra"
    tem_pesquisa = any(parecido(t, VERBOS_PESQUISA) for t in cl)

    # 1) Pesquisa: tudo depois da palavra "pesquisa/pesquise/procura"
    if tem_pesquisa:
        i = next(i for i, p in enumerate(cl) if parecido(p, VERBOS_PESQUISA))
        site = "youtube" if any(t in SITES_YOUTUBE for t in cl) else "google"
        termos = [t for t in cl[i + 1:] if t not in SITES_PALAVRAS]
        while termos and termos[0] in IGNORAR_INICIO:
            termos.pop(0)
        while termos and termos[-1] in IGNORAR_FIM:
            termos.pop()
        if termos:
            return [("pesquisar", " ".join(termos), site)], False

    # 2) Abrir programa(s) da lista (pode haver mais de um na mesma frase)
    nomes = achar_apps(" ".join(cl))
    if nomes:
        fraco = len(cl) <= MAX_PALAVRAS_FRACO and any(parecido(t, VERBOS_FRACOS) for t in cl)
        if tem_forte or fraco or len(cl) <= 2:
            return [("abrir_app", n, "google") for n in nomes], False

    # 3) Jogo da Steam ou programa do Menu Iniciar pelo nome (só com verbo forte)
    if tem_forte:
        termos = [t for t in cl if t not in SOBRA_NOME and not parecido(t, VERBOS_FORTES)]
        if termos:
            consulta = " ".join(termos)
            if achar_jogo(consulta, minimo=0.85):
                return [("abrir_jogo", consulta, "google")], False
            if achar_atalho(consulta, minimo=0.85):
                return [("abrir_programa", consulta, "google")], False

    return [], (tem_forte_proprio or tem_pesquisa)


def tentar_comando(texto):
    """Devolve ('fala', texto) | ('acoes', lista, restos) | None (aí o modelo resolve tudo)."""
    palavras = normalizar(texto)
    agora = datetime.now()

    if any(p in ("horas", "hora") for p in palavras) and \
            any(p in ("que", "quantas", "qual") for p in palavras):
        return ("fala", f"Agora são {agora:%H} e {agora:%M}, senhor.")
    if ("hoje" in palavras and any(p in ("dia", "data") for p in palavras)) or \
            ("semana" in palavras and "dia" in palavras):
        return ("fala", f"Hoje é {DIAS[agora.weekday()]}, {agora.day} de "
                        f"{MESES[agora.month - 1]}, senhor.")

    acoes, restos = [], []
    frase_tem_forte = any(p in VERBOS_FORTES for p in palavras)
    for pedido in dividir_em_pedidos(palavras):
        a, nao_entendido = acoes_do_pedido(pedido, frase_tem_forte)
        print(f"[camada 0: pedido={pedido} -> "
              f"{a if a else ('NÃO ENTENDIDO' if nao_entendido else 'ignorado')}]")
        acoes.extend(a)
        if nao_entendido:
            restos.append(" ".join(pedido))
    return ("acoes", acoes, restos) if acoes else None


# ---------------- OLLAMA SOB DEMANDA ----------------
_ollama_proc = None       # só existe se FOI O JARVIS que ligou o servidor
ultimo_uso_llm = 0.0
SEM_JANELA = 0x08000000   # CREATE_NO_WINDOW (não abre janela preta)


def ollama_no_ar():
    try:
        ollama.list()
        return True
    except Exception:
        return False


def achar_ollama_exe():
    exe = shutil.which("ollama")
    if exe:
        return exe
    cand = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
    return cand if os.path.exists(cand) else None


def garantir_ollama():
    """Liga o servidor do Ollama só quando precisa (se estiver desligado)."""
    global _ollama_proc, ultimo_uso_llm
    ultimo_uso_llm = time.time()
    if ollama_no_ar():
        return
    exe = achar_ollama_exe()
    if not exe:
        raise RuntimeError("não achei o Ollama instalado")
    ui_enviar("rotulo", "Ligando o modelo...")
    print("[ollama: ligando o servidor sob demanda]")
    _ollama_proc = subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, creationflags=SEM_JANELA)
    for _ in range(60):
        time.sleep(0.5)
        if ollama_no_ar():
            return
    raise RuntimeError("o Ollama não respondeu")


def desligar_ollama():
    """Desliga o servidor, mas só se foi o Jarvis que o ligou."""
    global _ollama_proc
    if _ollama_proc is None:
        return
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(_ollama_proc.pid)],
                       capture_output=True, creationflags=SEM_JANELA)
    except Exception:
        pass
    _ollama_proc = None
    print("[ollama: servidor desligado]")


def vigia_ollama():
    while True:
        time.sleep(30)
        if _ollama_proc is not None and time.time() - ultimo_uso_llm > OLLAMA_OCIOSO_MIN * 60:
            print("[ollama: parado há muito tempo, desligando]")
            desligar_ollama()


atexit.register(desligar_ollama)
try:  # também desliga se você fechar a janela preta no X
    import ctypes
    _HANDLER = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)(
        lambda ev: (desligar_ollama(), False)[1])
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_HANDLER, True)
except Exception:
    pass


# ---------------- MODELO (só planeja; quem age é o código) ----------------
def planejar(texto, historico):
    global ultimo_uso_llm
    garantir_ollama()
    msgs = [{"role": "system", "content": sistema_plano()}] + historico[1:]
    msgs.append({"role": "user", "content": texto})
    resp = ollama.chat(model=MODELO, messages=msgs, format=ESQUEMA_PLANO,
                       think=False, keep_alive=KEEP_ALIVE_MODELO,
                       options={"temperature": 0.2})
    ultimo_uso_llm = time.time()
    ui_enviar("estado", "pensando")
    bruto = resp.message.content
    print(f"[plano do modelo: {bruto}]")
    try:
        dados = json.loads(bruto)
    except Exception:
        return [], bruto.strip() or "Desculpe, senhor, não consegui entender."
    acoes = [(a.get("ferramenta", ""), (a.get("alvo") or "").strip(),
              a.get("site") or "google") for a in dados.get("acoes", [])]
    return acoes, (dados.get("resposta") or "").strip()


# ---------------- INICIALIZAÇÃO ----------------
carregar_meus_apps()
carregar_atalhos()
print(f"[{len(_ATALHOS)} atalhos do Menu Iniciar encontrados]")
print("Carregando modelos...")
stt = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
voz = PiperVoice.load(ARQUIVO_VOZ)
list(stt.transcribe(np.zeros(16000, dtype="float32"), language="pt")[0])
threading.Thread(target=vigia_ollama, daemon=True).start()
print(f"Pronto. ({len(jogos_instalados())} jogos da Steam encontrados)")

fila = queue.Queue()


def tocador():
    while True:
        audio, taxa = fila.get()
        sd.play(audio, taxa)
        sd.wait()
        fila.task_done()


threading.Thread(target=tocador, daemon=True).start()


def falar(texto, t_fim, marcas):
    """Fala o texto frase por frase (a primeira frase começa a tocar mais cedo)."""
    for frase in re.split(r"(?<=[.!?])\s+", texto.strip()):
        if not frase.strip():
            continue
        pedacos, taxa = [], 22050
        for c in voz.synthesize(para_fala(frase)):
            taxa = c.sample_rate
            pedacos.append(np.frombuffer(c.audio_int16_bytes, dtype=np.int16))
        if pedacos:
            marcas.setdefault("audio", time.time() - t_fim)
            fila.put((np.concatenate(pedacos), taxa))


historico = [{"role": "system", "content": SISTEMA}]


def processar(texto, t_fim, marcas):
    """Entende o pedido, executa, fala o resultado. Devolve o que foi falado."""
    global historico
    direta = tentar_comando(texto)
    origem = "camada 0"
    if direta and direta[0] == "fala":
        fala = direta[1]
    elif direta:
        _, acoes0, restos = direta
        extras, nao_entendi = [], []
        if restos:
            # O que a camada 0 não entendeu NÃO é descartado: o modelo tenta.
            resto_texto = " ".join(restos)
            print(f"[camada 0 não entendeu: {resto_texto!r} -> perguntando ao modelo]")
            acoes_m, _ = planejar(resto_texto, historico)
            if acoes_m:
                extras = acoes_m
            else:
                nao_entendi = restos
            origem = "camada 0 + modelo"
        fala = executar_lista(acoes0 + extras, nao_entendi)
    else:
        origem = "modelo"
        acoes, resposta = planejar(texto, historico)
        fala = executar_lista(acoes) if acoes else (resposta or "Pois não, senhor?")

    marcas["pronto"] = time.time() - t_fim
    ui_enviar("estado", "falando")
    ui_enviar("texto", f"Você: {texto}\n\nJarvis: {limpar_titulo(fala)}")
    falar(fala, t_fim, marcas)
    print(f"Jarvis: {fala}")
    print(f"[{origem} | texto {marcas['stt']:.2f}s | pronto {marcas['pronto']:.2f}s | "
          f"1º áudio pronto {marcas.get('audio', 0):.2f}s]")
    fila.join()
    time.sleep(0.4)  # deixa o eco das caixas de som passar
    historico.append({"role": "user", "content": texto})
    historico.append({"role": "assistant", "content": fala})
    historico = historico[:1] + historico[-8:]
    return fala


# ---------------- ENTRADA: ENTER/DIGITAR (modo antigo) ----------------
def gravar():
    """Devolve (áudio, instante do fim da fala, texto digitado)."""
    frames = []

    def cb(indata, n, t, s):
        frames.append(indata.copy())

    digitado = input("\nEnter = falar | ou DIGITE o comando e aperte Enter: ").strip()
    if digitado:
        return None, time.time(), digitado
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=cb):
        input("Falando... aperte Enter para parar.")
    t_fim = time.time()
    if not frames:
        return None, t_fim, None
    return np.concatenate(frames)[:, 0], t_fim, None


# ---------------- ENTRADA: ESCUTA AUTOMÁTICA (depois do F8) ----------------
BLOCO = int(16000 * 0.03)  # blocos de 30 ms


def calibrar_ruido():
    """Mede o ruído do ambiente por 1 segundo e define o limiar de voz."""
    print("Calibrando o ruído do ambiente (fique em silêncio por 1 segundo)...")
    gravacao = sd.rec(16000, samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    ambiente = float(np.sqrt(np.mean(gravacao ** 2)))
    limiar = max(LIMIAR_MINIMO, ambiente * 4)
    print(f"[escuta: ruído do ambiente={ambiente:.4f} | limiar de voz={limiar:.4f}]")
    return limiar


def ouvir_continuo(limiar, espera_max=None):
    """Espera você falar e devolve (áudio, instante do fim da fala).
    Devolve (None, agora) se você não falar nada em 'espera_max' segundos."""
    global nivel_mic
    blocos = queue.Queue()

    def cb(indata, n, t, s):
        blocos.put(indata[:, 0].copy())

    pre = collections.deque(maxlen=10)   # ~0,3 s antes de você começar a falar
    falando, frames, silencio, inicio, seguidos = False, [], 0.0, 0.0, 0
    comeco = time.time()
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                        blocksize=BLOCO, callback=cb):
        while True:
            if espera_max and not falando and time.time() - comeco > espera_max:
                nivel_mic = 0.0
                return None, time.time()
            try:
                b = blocos.get(timeout=0.2)
            except queue.Empty:
                continue
            nivel = float(np.sqrt(np.mean(b ** 2)))
            nivel_mic = nivel
            if not falando:
                pre.append(b)
                seguidos = seguidos + 1 if nivel > limiar else 0
                if seguidos >= 3:
                    falando, frames, silencio, inicio = True, list(pre), 0.0, time.time()
            else:
                frames.append(b)
                silencio = 0.0 if nivel > limiar else silencio + 0.03
                if silencio >= SILENCIO_FIM or time.time() - inicio > MAX_FALA:
                    audio = np.concatenate(frames)
                    if len(audio) < 16000 * 0.6:      # barulho curto: ignora
                        falando, frames, seguidos = False, [], 0
                        continue
                    nivel_mic = 0.0
                    return audio, time.time() - silencio


# ---------------- SESSÃO (F8 -> janela -> conversa -> janela fecha) ----------------
ativar = threading.Event()
limiar_voz = 0.0


def sessao_f8():
    ui_enviar("mostrar")
    ui_enviar("texto", "")
    ui_enviar("estado", "falando")
    saudacao = random.choice(SAUDACOES)
    ui_enviar("texto", f"Jarvis: {saudacao}")
    falar(saudacao, time.time(), {})
    fila.join()
    time.sleep(0.4)

    vazios = 0
    while True:
        ui_enviar("estado", "ouvindo")
        voz_usuario, t_fim = ouvir_continuo(limiar_voz, ESPERA_FALA)
        if voz_usuario is None:
            break                                   # ficou em silêncio: fecha a janela
        ui_enviar("estado", "pensando")
        segs, _ = stt.transcribe(voz_usuario, language="pt", vad_filter=True,
                                 initial_prompt=DICA)
        texto = " ".join(s.text for s in segs).strip()
        marcas = {"stt": time.time() - t_fim}
        print(f"Você: {texto or '(nada reconhecido)'}")
        if not texto:
            vazios += 1
            if vazios >= 2:
                break
            continue
        vazios = 0
        palavras = normalizar(texto)
        if texto.lower().strip(" .!") in ("sair", "encerrar", "jarvis sair"):
            desligar_ollama()
            os._exit(0)
        if len(palavras) <= 4 and any(p in DESPEDIDAS for p in palavras):
            ui_enviar("estado", "falando")
            ui_enviar("texto", f"Você: {texto}\n\nJarvis: Às ordens, senhor.")
            falar("Às ordens, senhor.", time.time(), {})
            fila.join()
            break
        ui_enviar("texto", f"Você: {texto}")
        processar(texto, t_fim, marcas)
    ui_enviar("esconder")


def trabalhador():
    while True:
        ativar.wait()
        ativar.clear()
        try:
            sessao_f8()
        except Exception:
            traceback.print_exc()
            ui_enviar("esconder")
        ativar.clear()   # ignora F8 apertado durante a sessão


# ---------------- LOOP PRINCIPAL ----------------
if MODO == "f8":
    if keyboard is None:
        print("Falta instalar a biblioteca da tecla. Rode: pip install keyboard")
        raise SystemExit
    ui = Interface()
    limiar_voz = calibrar_ruido()
    keyboard.add_hotkey(TECLA, ativar.set)
    threading.Thread(target=trabalhador, daemon=True).start()
    print(f"\nPronto! Aperte {TECLA.upper()} para chamar o Jarvis. (Feche esta janela para encerrar)")
    ui.root.mainloop()
else:
    while True:
        voz_usuario, t_fim, digitado = gravar()
        if digitado:
            texto = digitado
            marcas = {"stt": 0.0}
            print(f"Você (digitado): {texto}")
        else:
            if voz_usuario is None:
                continue
            segs, _ = stt.transcribe(voz_usuario, language="pt", vad_filter=True,
                                     initial_prompt=DICA)
            texto = " ".join(s.text for s in segs).strip()
            marcas = {"stt": time.time() - t_fim}
            print(f"Você: {texto or '(nada reconhecido)'}")
        if not texto:
            continue
        if texto.lower().strip(" .!") in ("sair", "encerrar"):
            break
        processar(texto, t_fim, marcas)
