import cv2
import queue
import threading
import time
import json
import os
import csv
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

import requests
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import serial
from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Constantes globais
# ---------------------------------------------------------------------------
CLASS_NAMES      = ['Blobbing', 'Cracks', 'Over Extrusion', 'Spaghetti', 'Stringing', 'Under Extrusion']
DISPLAY_W        = 860       # largura max do preview na UI
DISPLAY_H        = 540       # altura  max do preview na UI
DISPLAY_MS       = 40        # intervalo de refresh da UI (~25fps)
YOLO_INTERVALO_S = 0.5       # segundos minimos entre inferencias (~2fps)
YOLO_INPUT_W     = 640       # largura do frame enviado ao YOLO (menor = mais rapido)
CONF_THRESHOLD   = 0.5

csv_lock         = threading.Lock()
_app_encerrando  = False
# flag global para cancelar thread de vinculação do Telegram quando a janela fecha
_vincular_ativo  = {"ok": True}


# ---------------------------------------------------------------------------
# Thread 1 - CameraThread
# ---------------------------------------------------------------------------
class CameraThread:
    """Captura frames em background e expõe sempre o frame mais recente."""

    def __init__(self, url):
        self.url      = url
        self.ret      = False
        self.frame    = None
        self._lock    = threading.Lock()
        self._rodando = True
        self.cap      = None
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        FALHAS_PARA_RECONECTAR = 30   # ~3 s de falhas consecutivas
        self.cap = cv2.VideoCapture(self.url)
        falhas_consecutivas = 0
        while self._rodando:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                with self._lock:
                    self.ret = ret
                    if ret:
                        self.frame = frame
                if not ret:
                    falhas_consecutivas += 1
                    if falhas_consecutivas >= FALHAS_PARA_RECONECTAR:
                        print("[CameraThread] Muitas falhas consecutivas. Reabrindo conexao...")
                        self.cap.release()
                        time.sleep(2.0)
                        if self._rodando: # NOVO: Só reabre se o app não estiver fechando
                            self.cap = cv2.VideoCapture(self.url)
                        falhas_consecutivas = 0
                    else:
                        time.sleep(0.1)
                else:
                    falhas_consecutivas = 0
            else:
                time.sleep(0.5)
                if self._rodando: # NOVO: Só tenta conectar se o app não estiver fechando
                    self.cap = cv2.VideoCapture(self.url)
                    
        # NOVO: A thread se auto-limpa quando o loop termina, sem travar a tela principal!
        if self.cap:
            self.cap.release()

    def release(self):
        # NOVO: Apenas avisa para parar. Nunca bloqueia a tela principal!
        self._rodando = False

    def read(self):
        with self._lock:
            return self.ret, (self.frame.copy() if self.frame is not None else None)

    def isOpened(self):
        return self.cap is not None and self.cap.isOpened() and self.ret


# ---------------------------------------------------------------------------
# Thread 2 - YOLOWorker
# ---------------------------------------------------------------------------
class YOLOWorker(threading.Thread):
    """
    Roda inferencia YOLO em thread propria.
    Recebe frames via fila de 1 slot (sempre o mais recente).
    Nunca bloqueia a thread da UI.
    """

    def __init__(self, model):
        super().__init__(daemon=True)
        self._model     = model
        self._fila      = queue.Queue(maxsize=1)
        self._resultado = {"id": 0, "detectou": False, "classe": "", "caixas": []}
        self._lock_res  = threading.Lock()
        self._rodando   = True

    def enviar_frame(self, frame_yolo, offset_x, offset_y, escala_x, escala_y):
        """Envia frame para inferencia de forma nao-bloqueante."""
        payload = (frame_yolo, offset_x, offset_y, escala_x, escala_y)
        try:
            self._fila.put_nowait(payload)
        except queue.Full:
            try:
                self._fila.get_nowait()   # descarta frame antigo
                self._fila.put_nowait(payload)
            except queue.Empty:
                pass

    def resultado(self):
        """Retorna copia thread-safe do ultimo resultado."""
        with self._lock_res:
            return dict(self._resultado)

    def run(self):
        while self._rodando:
            try:
                frame_yolo, off_x, off_y, sx, sy = self._fila.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                detectou    = False
                classe      = ""
                caixas      = []
                melhor_conf = 0.0

                for r in self._model(frame_yolo, conf=CONF_THRESHOLD, verbose=False):
                    for box in r.boxes:
                        detectou = True
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        bx1 = int(bx1 * sx) + off_x
                        by1 = int(by1 * sy) + off_y
                        bx2 = int(bx2 * sx) + off_x
                        by2 = int(by2 * sy) + off_y
                        conf = float(box.conf[0])
                        idx  = int(box.cls[0])
                        nome = CLASS_NAMES[idx] if idx < len(CLASS_NAMES) else f"Classe_{idx}"
                        if conf > melhor_conf:
                            melhor_conf = conf
                            classe      = nome
                        caixas.append((bx1, by1, bx2, by2, nome, conf))

                with self._lock_res:
                    self._resultado = {
                        "id": time.time(), "detectou": detectou,
                        "classe": classe, "caixas": caixas
                    }

            except Exception as e:
                print(f"[ERRO] YOLOWorker falhou numa inferencia: {e}")
                with self._lock_res:
                    self._resultado = {
                        "id": time.time(), "detectou": False,
                        "classe": "", "caixas": []
                    }

    def parar(self):
        self._rodando = False


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------
def carregar_configuracoes():
    defaults = {
        "preferencia_notificacao": "Ambos",
        "telegram_token": "", "telegram_chat_id": "",
        "limite_persistencia": 30,
        "nome_laboratorio": "LabInd - Impressora 01",
        "email_remetente": "", "email_senha": "", "email_destino": "",
        "smtp_server": "smtp.gmail.com", "smtp_port": 587,
        "parar_automatica": False,
        "tipo_conexao": "BambuMQTT",
        "bambu_ip": "", "bambu_access_code": "", "bambu_serial": "",
        "serial_port": "COM3", "serial_gcode": "M112",
        "url_camera_custom": "0",
        "cooldown_alertas": 300,
        "roi": None
    }
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                defaults.update(json.load(f))
        except Exception as e:
            print(f"[AVISO] config.json invalido: {e}")
    return defaults


def salvar_configuracoes(cfg):
    """Salva config atomicamente via arquivo temporario (evita corrupcao em queda de energia)."""
    tmp = "config.json.tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=4)
        os.replace(tmp, "config.json")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar configuracoes: {e}")
        try:
            os.remove(tmp)
        except OSError:
            pass


def registrar_log_csv(tipo, impressora, evento="Falha Detectada"):
    caminho = "historico_falhas.csv"
    try:
        with csv_lock:
            existe = os.path.exists(caminho)
            with open(caminho, mode="a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if not existe:
                    w.writerow(["Data", "Hora", "Impressora", "Falha", "Evento"])
                agora = datetime.now()
                w.writerow([agora.strftime("%Y-%m-%d"), agora.strftime("%H:%M:%S"),
                            impressora, tipo, evento])
    except Exception as e:
        print(f"[ERRO] Falha ao escrever no CSV: {e}")


def obter_url_camera(config):
    if config.get("tipo_conexao") == "BambuMQTT":
        return (f"rtsps://bblp:{config.get('bambu_access_code','')}"
                f"@{config.get('bambu_ip','')}:322/streaming/live/1")
    cam = config.get("url_camera_custom", "0")
    return int(cam) if str(cam).isdigit() else cam


def executar_kill_switch(config):
    if not config.get("parar_automatica"):
        return
    if config["tipo_conexao"] == "BambuMQTT":
        try:
            c = mqtt.Client(CallbackAPIVersion.VERSION2)
            c.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)
            c.username_pw_set("bblp", config["bambu_access_code"])
            c.connect_async(config["bambu_ip"], 8883, 60)
            c.loop_start()
            deadline = time.time() + 8
            while not c.is_connected() and time.time() < deadline:
                time.sleep(0.1)
            if not c.is_connected():
                raise ConnectionError("Timeout ao conectar no MQTT da Bambu Lab")
            payload = {"print": {"sequence_id": "1", "command": "pause", "param": ""}}
            c.publish(f"device/{config['bambu_serial']}/request", json.dumps(payload), qos=1)
            time.sleep(1.5)
            c.loop_stop()
            c.disconnect()
            print("[OK] Pausa MQTT enviada.")
        except Exception as e:
            print(f"[ERRO] MQTT: {e}")
    elif config["tipo_conexao"] == "Serial":
        try:
            with serial.Serial(config["serial_port"], 115200, timeout=1) as ser:
                ser.write(f"{config['serial_gcode']}\r\n".encode())
            print(f"[OK] G-Code {config['serial_gcode']} enviado.")
        except Exception as e:
            print(f"[ERRO] Serial: {e}")


def _limpar_capturas_antigas(pasta="capturas", manter_ultimas=200):
    """Remove capturas antigas, mantendo apenas as N mais recentes."""
    try:
        arquivos = sorted(
            [os.path.join(pasta, f) for f in os.listdir(pasta) if f.endswith(".jpg")],
            key=os.path.getmtime
        )
        for antigo in arquivos[:-manter_ultimas]:
            os.remove(antigo)
    except Exception as e:
        print(f"[AVISO] Limpeza de capturas falhou: {e}")


def disparar_alertas_background(tipo, frame, config):
    """Executado em thread separada - nunca bloqueia a UI."""
    os.makedirs("capturas", exist_ok=True)
    _limpar_capturas_antigas()
    agora   = datetime.now()
    caminho = os.path.join("capturas", f"alerta_{agora.strftime('%Y%m%d_%H%M%S')}.jpg")
    imagem_salva = cv2.imwrite(caminho, frame)
    if not imagem_salva:
        print(f"[ERRO] Falha ao salvar imagem em {caminho}. Disco cheio?")
        caminho = None

    texto = f"FALHA: {tipo} | {config['nome_laboratorio']} | {agora.strftime('%H:%M:%S')}"
    registrar_log_csv(tipo, config["nome_laboratorio"])
    executar_kill_switch(config)

    pref = config.get("preferencia_notificacao", "Ambos")
    if pref in ("Telegram", "Ambos"):
        try:
            base = f"https://api.telegram.org/bot{config['telegram_token']}"
            cid  = config["telegram_chat_id"]
            requests.post(f"{base}/sendMessage",
                          data={"chat_id": cid, "text": texto}, timeout=10)
            if caminho and os.path.exists(caminho):
                with open(caminho, "rb") as f:
                    requests.post(f"{base}/sendPhoto",
                                  data={"chat_id": cid}, files={"photo": f}, timeout=10)
        except Exception as e:
            print(f"[AVISO] Telegram: {e}")

    if pref in ("Email", "Ambos"):
        try:
            msg = MIMEMultipart()
            msg["From"]    = config["email_remetente"]
            msg["To"]      = config["email_destino"]
            msg["Subject"] = texto
            msg.attach(MIMEText(texto, "plain", "utf-8"))
            if caminho and os.path.exists(caminho):
                with open(caminho, "rb") as f:
                    msg.attach(MIMEImage(f.read(), name="falha.jpg"))
            with smtplib.SMTP(config.get("smtp_server", "smtp.gmail.com"),
                              config.get("smtp_port", 587), timeout=10) as s:
                s.starttls()
                s.login(config["email_remetente"], config["email_senha"])
                s.send_message(msg)
        except Exception as e:
            print(f"[AVISO] Email: {e}")


# ---------------------------------------------------------------------------
# Seletor de ROI
# ---------------------------------------------------------------------------
def abrir_seletor_roi(cap, config):
    ret, frame = cap.read()
    if not ret or frame is None:
        messagebox.showerror("Erro", "Nao foi possivel capturar frame da camera.")
        return

    h_orig, w_orig = frame.shape[:2]
    MAX_W, MAX_H   = 900, 560
    esc = min(MAX_W / w_orig, MAX_H / h_orig)
    w_d, h_d = int(w_orig * esc), int(h_orig * esc)

    img_pil = Image.fromarray(
        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    ).resize((w_d, h_d), Image.LANCZOS)

    jan = tk.Toplevel()
    jan.title("Definir Area de Analise")
    jan.resizable(False, False)
    jan.attributes("-topmost", True)
    jan.grab_set()
    jan.configure(bg="#1a1a1a")

    tk.Label(jan, text="Arraste para marcar a area. CONFIRMAR para salvar.",
             bg="#1a1a1a", fg="white", font=("Roboto", 12), pady=6).pack(fill="x")

    canvas = tk.Canvas(jan, width=w_d, height=h_d, cursor="crosshair", bg="black")
    canvas.pack()
    tk_img = ImageTk.PhotoImage(img_pil)
    canvas.create_image(0, 0, anchor="nw", image=tk_img)
    canvas.tk_img = tk_img  # mantém referencia

    roi_ex = config.get("roi")
    if roi_ex:
        canvas.create_rectangle(
            int(roi_ex[0] * esc), int(roi_ex[1] * esc),
            int(roi_ex[2] * esc), int(roi_ex[3] * esc),
            outline="#00ff88", width=2, dash=(6, 3), tags="roi_atual"
        )

    st = {"x0": 0, "y0": 0, "rid": None, "roi_d": None}

    def press(e):
        st["x0"], st["y0"] = e.x, e.y
        if st["rid"]:
            canvas.delete(st["rid"])
        st["rid"] = canvas.create_rectangle(e.x, e.y, e.x, e.y,
                                             outline="#00ff00", width=2, dash=(5, 3))

    def drag(e):
        canvas.coords(st["rid"], st["x0"], st["y0"], e.x, e.y)

    def release(e):
        d = (min(st["x0"], e.x), min(st["y0"], e.y),
             max(st["x0"], e.x), max(st["y0"], e.y))
        st["roi_d"] = d
        lbl_c.configure(text=f"Area: {int((d[2]-d[0])/esc)} x {int((d[3]-d[1])/esc)} px")

    canvas.bind("<ButtonPress-1>",   press)
    canvas.bind("<B1-Motion>",       drag)
    canvas.bind("<ButtonRelease-1>", release)

    f_b   = tk.Frame(jan, bg="#1a1a1a"); f_b.pack(fill="x", pady=8)
    lbl_c = tk.Label(f_b, text="Nenhuma area selecionada",
                     bg="#1a1a1a", fg="#aaaaaa", font=("Roboto", 11))
    lbl_c.pack(side="left", padx=15)

    def confirmar():
        d = st["roi_d"]
        if d is None or (d[2]-d[0]) < 10 or (d[3]-d[1]) < 10:
            messagebox.showwarning("Aviso", "Selecione uma area maior."); return
        config["roi"] = [max(0, int(d[0]/esc)), max(0, int(d[1]/esc)),
                          min(w_orig, int(d[2]/esc)), min(h_orig, int(d[3]/esc))]
        salvar_configuracoes(config)
        jan.destroy()

    def limpar():
        config["roi"] = None
        salvar_configuracoes(config)
        st["roi_d"] = None
        if st["rid"]:
            canvas.delete(st["rid"])
        canvas.delete("roi_atual")
        lbl_c.configure(text="ROI removido - analisando frame inteiro")

    tk.Button(f_b, text="CONFIRMAR", command=confirmar,
              bg="#28a745", fg="white", font=("Roboto", 12, "bold"),
              relief="flat", padx=16, pady=6).pack(side="right", padx=10)
    tk.Button(f_b, text="Remover ROI", command=limpar,
              bg="#6c757d", fg="white", font=("Roboto", 11),
              relief="flat", padx=12, pady=6).pack(side="right", padx=4)
    tk.Button(f_b, text="Cancelar", command=jan.destroy,
              bg="#444444", fg="white", font=("Roboto", 11),
              relief="flat", padx=12, pady=6).pack(side="right", padx=4)

    jan.wait_window()


# ---------------------------------------------------------------------------
# Janela de Setup
# ---------------------------------------------------------------------------
def abrir_janela_setup(config_atual):
    global _vincular_ativo
    # ── Reseta a flag a cada abertura para que vincular_telegram funcione ──
    _vincular_ativo["ok"] = True

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    import tkinter as _tk
    is_top = False
    try:
        _tk._default_root.winfo_exists()
        root = ctk.CTkToplevel()
        root.grab_set()
        is_top = True
    except (AttributeError, _tk.TclError):
        root = ctk.CTk()

    root.title("Configuracao Industrial - LabInd")
    root.geometry("920x750")
    root.minsize(850, 700)

    var_notif = tk.StringVar(value=config_atual.get("preferencia_notificacao", "Ambos"))
    var_parar = tk.BooleanVar(value=config_atual.get("parar_automatica", False))
    var_hw    = tk.StringVar(value=config_atual.get("tipo_conexao", "BambuMQTT"))
    refs      = {}

    def atualizar_ui(*_):
        if not refs:
            return
        esc   = var_notif.get()
        st_tg = "normal" if esc in ("Telegram", "Ambos") else "disabled"
        st_em = "normal" if esc in ("Email", "Ambos")    else "disabled"
        for k in ("entry_token", "entry_id", "btn_vincular"):
            refs[k].configure(state=st_tg)
        for k in ("entry_rem", "entry_sen", "entry_des"):
            refs[k].configure(state=st_em)
        st_b = "normal" if var_hw.get() == "BambuMQTT" else "disabled"
        st_s = "normal" if var_hw.get() == "Serial"    else "disabled"
        for k in ("ent_bip", "ent_bcode", "ent_bser", "btn_testar"):
            refs[k].configure(state=st_b)
        for k in ("ent_sport", "ent_sgcode", "ent_scam"):
            refs[k].configure(state=st_s)

    def _fechar():
        _vincular_ativo["ok"] = False   # cancela thread de escuta do Telegram
        root.destroy()
        if not is_top:
            root.quit()

    def salvar():
        config_atual.update({
            "preferencia_notificacao": var_notif.get(),
            "telegram_token":          refs["entry_token"].get(),
            "telegram_chat_id":        refs["entry_id"].get(),
            "email_remetente":         refs["entry_rem"].get(),
            "email_senha":             refs["entry_sen"].get(),
            "email_destino":           refs["entry_des"].get(),
            "nome_laboratorio":        refs["entry_lab"].get(),
            "parar_automatica":        var_parar.get(),
            "tipo_conexao":            var_hw.get(),
            "bambu_ip":                refs["ent_bip"].get(),
            "bambu_access_code":       refs["ent_bcode"].get(),
            "bambu_serial":            refs["ent_bser"].get(),
            "serial_port":             refs["ent_sport"].get(),
            "serial_gcode":            refs["ent_sgcode"].get(),
            "url_camera_custom":       refs["ent_scam"].get(),
            "cooldown_alertas":        int(refs["entry_cool"].get())
                                       if refs["entry_cool"].get().isdigit() else 300,
            # smtp e limite não têm campo na UI — preserva valores existentes
            "smtp_server":             config_atual.get("smtp_server", "smtp.gmail.com"),
            "smtp_port":               config_atual.get("smtp_port", 587),
            "limite_persistencia":     config_atual.get("limite_persistencia", 30),
        })
        salvar_configuracoes(config_atual)
        _fechar()

    def fechar_sistema():
        global _app_encerrando
        _app_encerrando = True
        _fechar()

    def teste_bambu():
        try:
            c = mqtt.Client(CallbackAPIVersion.VERSION2)
            c.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)
            c.username_pw_set("bblp", refs["ent_bcode"].get())
            c.connect(refs["ent_bip"].get(), 8883, 5)
            messagebox.showinfo("Sucesso", "Conexao estabelecida!\nA impressora respondeu.")
            c.disconnect()
        except Exception as e:
            messagebox.showerror("Falha", f"Sem conexao:\n{e}")

    def vincular_telegram():
        token = refs["entry_token"].get()
        if not token:
            messagebox.showwarning("Aviso", "Insira o Token primeiro!"); return

        def escutar():
            if not _vincular_ativo["ok"]:
                return
            try:
                init   = requests.get(
                    f"https://api.telegram.org/bot{token}/getUpdates?offset=-1",
                    timeout=5).json()
                offset = ((init["result"][-1]["update_id"] + 1)
                          if init.get("ok") and init["result"] else 0)
            except Exception:
                offset = 0
            for _ in range(30):
                if not _vincular_ativo["ok"]:
                    return
                time.sleep(2)
                try:
                    resp = requests.get(
                        f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}",
                        timeout=5).json()
                    if resp.get("ok") and resp["result"]:
                        nid    = str(resp["result"][-1]["message"]["chat"]["id"])
                        offset = resp["result"][-1]["update_id"] + 1
                        if _vincular_ativo["ok"]:
                            root.after(0, lambda n=nid: (
                                refs["entry_id"].delete(0, "end"),
                                refs["entry_id"].insert(0, n)
                            ))
                            root.after(0, lambda: refs["lbl_tg_status"].configure(
                                text="Vinculado!", text_color="#28a745"))
                        return
                except Exception:
                    continue

        try:
            r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5).json()
            if r.get("ok"):
                refs["lbl_tg_status"].configure(
                    text="Aguardando mensagem no bot...", text_color="#f39c12")
                threading.Thread(target=escutar, daemon=True).start()
        except Exception:
            refs["lbl_tg_status"].configure(
                text="Erro de Token/Rede", text_color="#dc3545")

    # ── escanear_cameras: deve ficar AQUI dentro para ter acesso a `root` ──
    def escanear_cameras():
        def _scan():
            found = []
            for i in range(6):
                bk = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
                ct = cv2.VideoCapture(i, bk)
                if ct.isOpened():
                    found.append(str(i))
                    ct.release()
            if found:
                root.after(0, lambda: messagebox.showinfo(
                    "Cameras",
                    f"Indices encontrados: {', '.join(found)}\n\n"
                    "Digite o correto no campo Camera."))
            else:
                root.after(0, lambda: messagebox.showwarning(
                    "Cameras", "Nenhuma camera local detectada."))
        threading.Thread(target=_scan, daemon=True).start()

    root.protocol("WM_DELETE_WINDOW", _fechar)

    # ------ Layout ------
    ctk.CTkLabel(root, text="Configuracoes do Sistema",
                 font=("Roboto", 24, "bold")).pack(pady=(15, 10))

    f_nome = ctk.CTkFrame(root, fg_color="transparent")
    f_nome.pack(fill="x", padx=40, pady=(0, 10))
    ctk.CTkLabel(f_nome, text="Nome do Equipamento:",
                 font=("Roboto", 14, "bold")).pack(side="left", padx=(0, 10))
    refs["entry_lab"] = ctk.CTkEntry(f_nome, width=300)
    refs["entry_lab"].insert(0, config_atual.get("nome_laboratorio", ""))
    refs["entry_lab"].pack(side="left", fill="x", expand=True)

    tabs    = ctk.CTkTabview(root)
    tabs.pack(padx=20, pady=5, fill="both", expand=True)
    t_notif = tabs.add("Notificacoes")
    t_hard  = tabs.add("Hardware e Controle")

    # -- Aba Notificacoes --
    f_rad = ctk.CTkFrame(t_notif, fg_color="transparent")
    f_rad.pack(pady=10)
    ctk.CTkLabel(f_rad, text="Alertas via:", font=("Roboto", 14)).pack(side="left", padx=15)
    for txt, val in [("Telegram", "Telegram"), ("E-mail", "Email"), ("Ambos", "Ambos")]:
        ctk.CTkRadioButton(f_rad, text=txt, variable=var_notif, value=val,
                           command=atualizar_ui).pack(side="left", padx=15)

    f_split = ctk.CTkFrame(t_notif, fg_color="transparent")
    f_split.pack(fill="both", expand=True, padx=10)
    col_e = ctk.CTkFrame(f_split, fg_color="transparent")
    col_e.pack(side="left", fill="both", expand=True, padx=(0, 10))
    col_d = ctk.CTkFrame(f_split, width=190, fg_color="#2b2b2b", corner_radius=10)
    col_d.pack(side="right", fill="y")

    # Telegram
    ctk.CTkLabel(col_e, text="Telegram", font=("Roboto", 15, "bold"),
                 text_color="#0088cc").pack(anchor="w", pady=(5, 2))
    ctk.CTkLabel(col_e, text="Token do Bot:").pack(anchor="w")
    refs["entry_token"] = ctk.CTkEntry(col_e, placeholder_text="Cole o token aqui")
    refs["entry_token"].insert(0, config_atual.get("telegram_token", ""))
    refs["entry_token"].pack(fill="x", pady=(0, 6))
    ctk.CTkLabel(col_e, text="Chat ID:").pack(anchor="w")
    refs["entry_id"] = ctk.CTkEntry(col_e)
    refs["entry_id"].insert(0, config_atual.get("telegram_chat_id", ""))
    refs["entry_id"].pack(fill="x", pady=(0, 12))

    ctk.CTkLabel(col_d, text="Vincular Conta",
                 font=("Roboto", 13, "bold")).pack(pady=(12, 6))
    refs["btn_vincular"] = ctk.CTkButton(col_d, text="Vincular via Bot",
                                          command=vincular_telegram, width=150)
    refs["btn_vincular"].pack(pady=4)
    refs["lbl_tg_status"] = ctk.CTkLabel(col_d, text="", font=("Roboto", 11),
                                          wraplength=160)
    refs["lbl_tg_status"].pack(padx=8, pady=4)
    ctk.CTkLabel(col_d,
                 text="1. Crie o bot no @BotFather\n2. Cole o token\n3. Clique Vincular\n4. Envie /start ao bot",
                 font=("Roboto", 11), text_color="#aaaaaa",
                 justify="left").pack(padx=10, pady=(4, 12))

    # Email
    ctk.CTkFrame(col_e, height=2, fg_color="#444444").pack(fill="x", pady=8)
    ctk.CTkLabel(col_e, text="E-mail (Gmail)", font=("Roboto", 15, "bold"),
                 text_color="#4285F4").pack(anchor="w", pady=(0, 4))
    f_er  = ctk.CTkFrame(col_e, fg_color="transparent"); f_er.pack(fill="x")
    c_rem = ctk.CTkFrame(f_er, fg_color="transparent")
    c_rem.pack(side="left", fill="x", expand=True, padx=(0, 5))
    ctk.CTkLabel(c_rem, text="Remetente:").pack(anchor="w")
    refs["entry_rem"] = ctk.CTkEntry(c_rem, placeholder_text="seuemail@gmail.com")
    refs["entry_rem"].insert(0, config_atual.get("email_remetente", ""))
    refs["entry_rem"].pack(fill="x")
    c_sen = ctk.CTkFrame(f_er, fg_color="transparent")
    c_sen.pack(side="left", fill="x", expand=True, padx=(5, 0))
    ctk.CTkLabel(c_sen, text="Senha de App (16 chars):").pack(anchor="w")
    refs["entry_sen"] = ctk.CTkEntry(c_sen, show="*")
    refs["entry_sen"].insert(0, config_atual.get("email_senha", ""))
    refs["entry_sen"].pack(fill="x")

    ctk.CTkLabel(col_e, text="Destino:").pack(anchor="w", pady=(8, 0))
    refs["entry_des"] = ctk.CTkEntry(col_e)
    refs["entry_des"].insert(0, config_atual.get("email_destino", ""))
    refs["entry_des"].pack(fill="x")
    ctk.CTkLabel(col_e, text="Cooldown entre alertas (segundos):").pack(anchor="w", pady=(8, 0))
    refs["entry_cool"] = ctk.CTkEntry(col_e)
    refs["entry_cool"].insert(0, str(config_atual.get("cooldown_alertas", 300)))
    refs["entry_cool"].pack(fill="x")

    # -- Aba Hardware --
    f_ht = ctk.CTkFrame(t_hard, fg_color="transparent")
    f_ht.pack(fill="x", padx=20, pady=15)
    ctk.CTkCheckBox(f_ht, text="Ativar Parada Automatica ao detectar falha",
                    variable=var_parar, command=atualizar_ui,
                    font=("Roboto", 14, "bold"),
                    text_color="#f39c12").pack(anchor="w")

    f_bambu = ctk.CTkFrame(t_hard, fg_color="#2b2b2b", corner_radius=10)
    f_bambu.pack(fill="x", padx=20, pady=8)
    ctk.CTkRadioButton(f_bambu, text="Bambu Lab (MQTT)", variable=var_hw,
                       value="BambuMQTT", command=atualizar_ui,
                       font=("Roboto", 14)).grid(row=0, column=0, columnspan=5,
                                                 sticky="w", padx=15, pady=(12, 8))
    ctk.CTkLabel(f_bambu, text="IP:").grid(row=1, column=0, sticky="e", padx=(15, 5))
    refs["ent_bip"] = ctk.CTkEntry(f_bambu, width=130)
    refs["ent_bip"].insert(0, config_atual.get("bambu_ip", ""))
    refs["ent_bip"].grid(row=1, column=1, sticky="w")
    ctk.CTkLabel(f_bambu, text="PIN/Code:").grid(row=1, column=2, sticky="e", padx=(20, 5))
    refs["ent_bcode"] = ctk.CTkEntry(f_bambu, width=110, show="*")
    refs["ent_bcode"].insert(0, config_atual.get("bambu_access_code", ""))
    refs["ent_bcode"].grid(row=1, column=3, sticky="w")
    refs["btn_testar"] = ctk.CTkButton(f_bambu, text="Testar", command=teste_bambu,
                                        width=90, fg_color="#d35400", hover_color="#e67e22")
    refs["btn_testar"].grid(row=1, column=4, padx=(15, 15), pady=5)
    ctk.CTkLabel(f_bambu, text="Serial Number:").grid(row=2, column=0, sticky="e",
                                                       padx=(15, 5), pady=(5, 12))
    refs["ent_bser"] = ctk.CTkEntry(f_bambu, width=300)
    refs["ent_bser"].insert(0, config_atual.get("bambu_serial", ""))
    refs["ent_bser"].grid(row=2, column=1, columnspan=4, sticky="w", pady=(5, 12))

    f_serial = ctk.CTkFrame(t_hard, fg_color="#2b2b2b", corner_radius=10)
    f_serial.pack(fill="x", padx=20, pady=8)
    ctk.CTkRadioButton(f_serial, text="Serial (USB/Marlin/Ender)", variable=var_hw,
                       value="Serial", command=atualizar_ui,
                       font=("Roboto", 14)).grid(row=0, column=0, columnspan=4,
                                                 sticky="w", padx=15, pady=(12, 8))
    ctk.CTkLabel(f_serial, text="Porta (ex: COM3):").grid(row=1, column=0,
                                                           sticky="e", padx=(15, 5))
    refs["ent_sport"] = ctk.CTkEntry(f_serial, width=100)
    refs["ent_sport"].insert(0, config_atual.get("serial_port", ""))
    refs["ent_sport"].grid(row=1, column=1, sticky="w")
    ctk.CTkLabel(f_serial, text="G-Code:").grid(row=1, column=2, sticky="e", padx=(20, 5))
    refs["ent_sgcode"] = ctk.CTkEntry(f_serial, width=100)
    refs["ent_sgcode"].insert(0, config_atual.get("serial_gcode", "M112"))
    refs["ent_sgcode"].grid(row=1, column=3, sticky="w", pady=(5, 10))

    f_cam = ctk.CTkFrame(f_serial, fg_color="transparent")
    f_cam.grid(row=2, column=0, columnspan=5, sticky="ew", padx=10, pady=(0, 12))
    ctk.CTkLabel(f_cam, text="Camera:", font=("Roboto", 13)).pack(side="left", padx=(0, 6))
    refs["ent_scam"] = ctk.CTkEntry(f_cam, width=70, placeholder_text="0 ou 1")
    refs["ent_scam"].insert(0, str(config_atual.get("url_camera_custom", "0")))
    refs["ent_scam"].pack(side="left")
    ctk.CTkLabel(f_cam, text=" <- 0=embutida  1=USB  ou URL RTSP",
                 font=("Roboto", 11), text_color="#888888").pack(side="left", padx=6)
    ctk.CTkButton(f_cam, text="Detectar", command=escanear_cameras,
                  width=90, height=26, fg_color="#555",
                  hover_color="#666").pack(side="left", padx=6)

    f_bot = ctk.CTkFrame(root, fg_color="transparent"); f_bot.pack(pady=(5, 15))
    ctk.CTkButton(f_bot, text="SALVAR E INICIAR", command=salvar,
                  fg_color="#28a745", font=("Roboto", 14, "bold"),
                  width=170, height=45).pack(side="left", padx=8)
    ctk.CTkButton(f_bot, text="VOLTAR", command=_fechar,
                  fg_color="#555555", font=("Roboto", 14, "bold"),
                  width=140, height=45).pack(side="left", padx=8)
    ctk.CTkButton(f_bot, text="ENCERRAR SISTEMA", command=fechar_sistema,
                  fg_color="#dc3545", font=("Roboto", 14, "bold"),
                  width=170, height=45).pack(side="left", padx=8)

    atualizar_ui()
    if is_top:
        root.wait_window()
    else:
        root.mainloop()


# ---------------------------------------------------------------------------
# Janela principal do monitor
# ---------------------------------------------------------------------------
def iniciar_app(config, cap, yolo_worker, model):
    """
    UI principal com loop via app.after(DISPLAY_MS).
    A thread da UI nunca bloqueia: display a ~25fps, YOLO a ~2fps em thread propria.
    """
    ctk.set_appearance_mode("dark")
    app = ctk.CTk()
    app.title(f"Monitor LabInd - {config.get('nome_laboratorio', '')}")
    app.geometry("1080x650")

    limite = config.get("limite_persistencia", 30)

    st = {
        "contador":       0,
        "confirmado":     False,
        "ultima_classe":  "",
        "falhas_rede":    0,
        "ultimo_alerta":  0.0,
        "ultimo_yolo":    0.0,
        "ultimo_id_yolo": 0,
        "cap":            cap,
        "yolo":           yolo_worker,
        "config":         config,
        "encerrando":     False,
        "reconectando":   False,
    }

    # --- Layout ---
    f_menu  = ctk.CTkFrame(app, width=300, corner_radius=0, fg_color="#212121")
    f_menu.pack(side="left", fill="y"); f_menu.pack_propagate(False)
    f_video = ctk.CTkFrame(app, fg_color="transparent")
    f_video.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    ctk.CTkLabel(f_menu, text="Painel de Controle",
                 font=("Roboto", 20, "bold")).pack(pady=(25, 15))
    lbl_status = ctk.CTkLabel(f_menu, text="Iniciando...",
                               font=("Roboto", 17, "bold"), text_color="#17a2b8")
    lbl_status.pack(pady=(5, 3))
    lbl_falha = ctk.CTkLabel(f_menu, text=f"Falhas: 0/{limite}", font=("Roboto", 15))
    lbl_falha.pack(pady=3)
    lbl_rede  = ctk.CTkLabel(f_menu, text="Camera: conectando...",
                              font=("Roboto", 13), text_color="gray")
    lbl_rede.pack(pady=(3, 5))

    roi_ativo = config.get("roi") is not None
    lbl_roi   = ctk.CTkLabel(f_menu,
                              text="ROI: Ativo" if roi_ativo else "ROI: Frame inteiro",
                              font=("Roboto", 12),
                              text_color="#00cc66" if roi_ativo else "#888888")
    lbl_roi.pack(pady=(0, 5))

    lbl_cool = ctk.CTkLabel(f_menu, text="", font=("Roboto", 12), text_color="#f39c12")
    lbl_cool.pack(pady=(0, 8))

    def acao_falso_positivo():
        cl = st["ultima_classe"] or "Desconhecida"
        registrar_log_csv(cl, st["config"]["nome_laboratorio"], evento="Falso Positivo")
        st.update({"contador": 0, "confirmado": False, "ultima_classe": ""})
        btn_fp.configure(state="disabled")
        lbl_status.configure(text="Operando Normal", text_color="#28a745")
        lbl_falha.configure(text=f"Falhas: 0/{limite}")
        lbl_cool.configure(text="")

    btn_fp = ctk.CTkButton(f_menu, text="Falso Positivo / Ignorar",
                           command=acao_falso_positivo,
                           fg_color="#6c757d", hover_color="#5a6268",
                           height=40, font=("Roboto", 13, "bold"), state="disabled")
    btn_fp.pack(padx=15, pady=(0, 10), fill="x")
    ctk.CTkFrame(f_menu, height=1, fg_color="#444444").pack(fill="x", padx=15, pady=5)

    flags = {"cmd": None}
    def _cmd(v): flags["cmd"] = v

    ctk.CTkButton(f_menu, text="Definir Area de Analise",
                  command=lambda: _cmd("roi"),
                  fg_color="#1a6b9a", hover_color="#155a80",
                  height=40, font=("Roboto", 13, "bold")).pack(padx=15, pady=5, fill="x")
    ctk.CTkButton(f_menu, text="Configuracoes",
                  command=lambda: _cmd("setup"),
                  fg_color="#f39c12", hover_color="#e67e22",
                  height=42, font=("Roboto", 14, "bold")).pack(
                      side="bottom", pady=(10, 15), padx=15, fill="x")
    ctk.CTkButton(f_menu, text="Encerrar",
                  command=lambda: _cmd("sair"),
                  fg_color="#dc3545", hover_color="#c82333",
                  height=42, font=("Roboto", 14, "bold")).pack(
                      side="bottom", pady=0, padx=15, fill="x")

    lbl_cam = ctk.CTkLabel(f_video, text=""); lbl_cam.pack(fill="both", expand=True)
    app.protocol("WM_DELETE_WINDOW", lambda: _cmd("sair"))

    # ---- Loop principal ----
    def loop():
        nonlocal limite, config

        if st["encerrando"]:
            return

        cmd = flags["cmd"]

        # Comando: abrir configuracoes
        if cmd == "setup":
            flags["cmd"] = None
            app.withdraw()
            st["cap"].release()
            st["yolo"].parar()
            abrir_janela_setup(config)

            if _app_encerrando:
                st["encerrando"] = True
                try: app.destroy()
                except Exception: pass
                return

            config       = carregar_configuracoes()
            st["config"] = config
            limite       = config.get("limite_persistencia", 30)
            novo_cap     = CameraThread(obter_url_camera(config))
            novo_yolo    = YOLOWorker(model); novo_yolo.start()
            st["cap"]    = novo_cap
            st["yolo"]   = novo_yolo
            st["falhas_rede"]    = 0
            st["ultimo_id_yolo"] = 0
            roi_a = config.get("roi") is not None
            lbl_roi.configure(text="ROI: Ativo" if roi_a else "ROI: Frame inteiro",
                              text_color="#00cc66" if roi_a else "#888888")
            lbl_falha.configure(text=f"Falhas: 0/{limite}")
            app.deiconify()
            app.after(DISPLAY_MS, loop); return

        # Comando: definir ROI
        if cmd == "roi":
            flags["cmd"] = None
            abrir_seletor_roi(st["cap"], config)
            config       = carregar_configuracoes()
            st["config"] = config
            limite       = config.get("limite_persistencia", 30)
            roi_a = config.get("roi") is not None
            lbl_roi.configure(text="ROI: Ativo" if roi_a else "ROI: Frame inteiro",
                              text_color="#00cc66" if roi_a else "#888888")
            app.after(DISPLAY_MS, loop); return

        # Comando: encerrar
        if cmd == "sair":
            st["encerrando"] = True
            st["cap"].release()
            st["yolo"].parar()
            try: app.destroy()
            except Exception: pass
            return

        # ---- Captura frame mais recente ----
        ret, img = st["cap"].read()

        if not ret or img is None:
            if not st.get("reconectando", False):
                st["falhas_rede"] += 1
                n = st["falhas_rede"]
                lbl_rede.configure(text=f"Camera: sem sinal ({n}/30)", text_color="#f39c12")
                if n > 30:
                    lbl_rede.configure(text="Camera: reconectando...", text_color="#dc3545")
                    st["reconectando"]   = True
                    st["falhas_rede"]    = 0
                    st["ultimo_id_yolo"] = 0
                    st["contador"]       = 0
                    st["cap"].release()
                    st["yolo"].parar()
                    st["cap"]  = CameraThread(obter_url_camera(config))
                    novo_yolo  = YOLOWorker(model); novo_yolo.start()
                    st["yolo"] = novo_yolo
            app.after(DISPLAY_MS, loop); return

        # Chegou aqui? A imagem voltou a funcionar!
        st["reconectando"] = False
        st["falhas_rede"]  = 0
        lbl_rede.configure(text="Camera: OK", text_color="#28a745")
        h_orig, w_orig = img.shape[:2]
        agora = time.time()

        # ---- Envia para YOLO no intervalo configurado ----
        if agora - st["ultimo_yolo"] >= YOLO_INTERVALO_S:
            st["ultimo_yolo"] = agora
            roi = config.get("roi")
            if roi and len(roi) == 4:
                rx1, ry1, rx2, ry2 = roi
                rx1 = max(0, min(rx1, w_orig - 1))
                ry1 = max(0, min(ry1, h_orig - 1))
                rx2 = max(rx1 + 1, min(rx2, w_orig))
                ry2 = max(ry1 + 1, min(ry2, h_orig))
                crop   = img[ry1:ry2, rx1:rx2]
                ch, cw = crop.shape[:2]
                yw     = YOLO_INPUT_W
                yh     = max(32, int(ch * yw / max(cw, 1)))
                fy     = cv2.resize(crop, (yw, yh), interpolation=cv2.INTER_LINEAR)
                st["yolo"].enviar_frame(fy, rx1, ry1, cw / yw, ch / yh)
            else:
                yw = YOLO_INPUT_W
                yh = max(32, int(h_orig * yw / max(w_orig, 1)))
                fy = cv2.resize(img, (yw, yh), interpolation=cv2.INTER_LINEAR)
                st["yolo"].enviar_frame(fy, 0, 0, w_orig / yw, h_orig / yh)

        # ---- Obtem ultimo resultado YOLO e anota frame ----
        res      = st["yolo"].resultado()
        detectou = res["detectou"]
        classe   = res["classe"]

        for (bx1, by1, bx2, by2, nome, conf) in res["caixas"]:
            lbl  = f"{nome} {conf:.0%}"
            lw   = len(lbl) * 11
            cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 0, 255), 2)
            cv2.rectangle(img, (bx1, by1 - 22), (bx1 + lw, by1), (0, 0, 255), -1)
            cv2.putText(img, lbl, (bx1 + 3, by1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        roi = config.get("roi")
        if roi and len(roi) == 4:
            rx1, ry1, rx2, ry2 = roi
            cv2.rectangle(img, (rx1, ry1), (rx2, ry2), (0, 220, 100), 1)
            cv2.putText(img, "ANALISE", (rx1 + 4, ry1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 100), 1)

        # ---- Logica de persistencia ----
        cnt     = st["contador"]
        novo_id = res.get("id", 0)

        if novo_id != st["ultimo_id_yolo"]:
            st["ultimo_id_yolo"] = novo_id
            cnt = min(limite, cnt + 1) if detectou else max(0, cnt - 1)
            st["contador"] = cnt

        t_desde  = agora - st["ultimo_alerta"]
        cooldown = config.get("cooldown_alertas", 300)
        em_cool  = t_desde < cooldown

        if cnt >= limite and not st["confirmado"]:
            if not em_cool:
                threading.Thread(target=disparar_alertas_background,
                                 args=(classe, img.copy(), config),
                                 daemon=True).start()
                st["ultimo_alerta"] = agora
                lbl_cool.configure(text="")
                st["confirmado"]    = True
                st["ultima_classe"] = classe
                btn_fp.configure(state="normal")

        elif cnt > 0 and detectou and classe != st["ultima_classe"]:
            st["confirmado"] = False; st["ultima_classe"] = ""
        elif cnt == 0:
            st["confirmado"] = False; st["ultima_classe"] = ""
            btn_fp.configure(state="disabled")

        if em_cool:
            rest = int(cooldown - t_desde)
            lbl_cool.configure(text=f"Cooldown: {rest // 60}m{rest % 60:02d}s")
        else:
            lbl_cool.configure(text="")

        lbl_status.configure(
            text=f"ALERTA: {classe}" if detectou else "Operando Normal",
            text_color="#dc3545" if detectou else "#28a745")
        lbl_falha.configure(text=f"Falhas: {cnt}/{limite}")

        # ---- Exibe frame (resize + conversao uma unica vez) ----
        esc   = min(DISPLAY_W / w_orig, DISPLAY_H / h_orig)
        nw    = int(w_orig * esc)
        nh    = int(h_orig * esc)
        small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        pil   = Image.fromarray(rgb)
        ctki  = ctk.CTkImage(light_image=pil, dark_image=pil, size=(nw, nh))
        lbl_cam.configure(image=ctki)
        lbl_cam._img_ref = ctki   # previne garbage collection

        app.after(DISPLAY_MS, loop)

    app.after(DISPLAY_MS, loop)
    app.mainloop()


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    config = carregar_configuracoes()

    # Abre setup na primeira execucao (sem notificacao configurada)
    if not config.get("telegram_token") and not config.get("email_remetente"):
        abrir_janela_setup(config)
        config = carregar_configuracoes()
        if _app_encerrando:
            exit(0)

    print("Carregando modelo YOLO...")
    model = YOLO("models/best.pt")
    print("[OK] Modelo carregado.")

    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;tcp|tls_verify;0|fflags;nobuffer|flags;low_delay|stimeout;5000000"
    )

    url_camera = obter_url_camera(config)
    print(f"Conectando a camera: "
          f"{url_camera if isinstance(url_camera, str) else f'indice {url_camera}'}")

    cap = CameraThread(url_camera)
    
    print("[OK] Monitor iniciado. A camera conectara em background.")

    yolo_worker = YOLOWorker(model)
    yolo_worker.start()

    iniciar_app(config, cap, yolo_worker, model)
