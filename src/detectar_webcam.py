import cv2
from ultralytics import YOLO
import requests
from datetime import datetime
import json
import os
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import time
import webbrowser
import qrcode
import csv
from PIL import ImageTk, Image
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# Bibliotecas para Hardware
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import serial 

# --- CLASSE PARA LEITURA DE VÍDEO EM PARALELO (ANTI-TRAVAMENTO) ---
class CameraThread:
    def __init__(self, url):
        self.url = url
        self.cap = cv2.VideoCapture(self.url)
        self.ret, self.frame = self.cap.read()
        self.rodando = True
        self.thread = threading.Thread(target=self.atualizar, daemon=True)
        self.thread.start()

    def atualizar(self):
        while self.rodando:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.ret = ret
                    self.frame = frame
            time.sleep(0.01)

    def read(self):
        return self.ret, self.frame

    def release(self):
        self.rodando = False
        self.cap.release()
        
    def isOpened(self):
        return self.cap.isOpened()

def guia_telegram():
    janela = ctk.CTkToplevel()
    janela.title("Ajuda - Configurar Telegram")
    janela.geometry("550x420")
    janela.attributes("-topmost", True)
    
    texto = (
        "🤖 PASSO A PASSO TELEGRAM:\n\n"
        "1. Abra o Telegram e procure por @BotFather.\n"
        "2. Envie o comando /newbot e siga as instruções.\n"
        "3. Copie o 'API Token' gerado e cole no campo do Setup.\n"
        "4. Inicie uma conversa com seu novo bot.\n"
        "5. Clique em 'Vincular QR Code' e escaneie com o celular."
    )
    ctk.CTkLabel(janela, text=texto, justify="left", font=("Roboto", 15)).pack(padx=20, pady=(30, 20))
    ctk.CTkButton(janela, text="Abrir @BotFather no Navegador", 
                  command=lambda: webbrowser.open("https://t.me/botfather"), 
                  fg_color="#0088cc", hover_color="#0077b3", font=("Roboto", 14, "bold"), height=40).pack(pady=10)
    ctk.CTkButton(janela, text="Fechar", command=janela.destroy, 
                  fg_color="#555555", hover_color="#333333", font=("Roboto", 14), height=40).pack(pady=10)

def guia_email():
    janela = ctk.CTkToplevel()
    janela.title("Ajuda - Senha de App Google")
    janela.geometry("550x450")
    janela.attributes("-topmost", True)
    
    texto = (
        "📧 PASSO A PASSO E-MAIL (GMAIL):\n\n"
        "1. Ative a 'Verificação em Duas Etapas' na sua conta Google.\n"
        "2. Vá em 'Segurança' > 'Senhas de App'.\n"
        "3. Em 'App', selecione 'Outro' e dê o nome 'LabInd'.\n"
        "4. O Google gerará uma senha de 16 caracteres.\n"
        "5. COPIE ESSA SENHA e cole no campo 'Senha de App'.\n\n"
        "⚠️ Importante: Não use sua senha normal do e-mail!"
    )
    ctk.CTkLabel(janela, text=texto, justify="left", font=("Roboto", 15)).pack(padx=20, pady=(30, 20))
    ctk.CTkButton(janela, text="Ir para Senhas de App (Google)", 
                  command=lambda: webbrowser.open("https://myaccount.google.com/apppasswords"), 
                  fg_color="#4285F4", hover_color="#3367d6", font=("Roboto", 14, "bold"), height=40).pack(pady=10)
    ctk.CTkButton(janela, text="Fechar", command=janela.destroy, 
                  fg_color="#555555", hover_color="#333333", font=("Roboto", 14), height=40).pack(pady=10)

def carregar_configuracoes():
    defaults = {
        "preferencia_notificacao": "Ambos",
        "telegram_token": "", "telegram_chat_id": "", "limite_persistencia": 30,
        "nome_laboratorio": "LabInd - Impressora 01",
        "email_remetente": "", "email_senha": "", "email_destino": "",
        "smtp_server": "smtp.gmail.com", "smtp_port": 587,
        "parar_automatica": False,
        "tipo_conexao": "BambuMQTT",
        "bambu_ip": "192.168.100.81",
        "bambu_access_code": "",
        "bambu_serial": "",
        "serial_port": "COM3",
        "serial_gcode": "M112"
    }
    caminho_config = 'config.json'
    if os.path.exists(caminho_config):
        with open(caminho_config, 'r') as f:
            try:
                config_salva = json.load(f)
                defaults.update(config_salva)
            except: pass
    return defaults

def registrar_log_csv(tipo, impressora):
    caminho_log = 'historico_falhas.csv'
    existe = os.path.exists(caminho_log)
    with open(caminho_log, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(['Data', 'Hora', 'Impressora', 'Falha'])
        writer.writerow([datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%H:%M:%S'), impressora, tipo])

def abrir_janela_setup(config_atual):
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    root.title("Configuração Industrial - LabInd")
    root.geometry("750x650") 

    var_escolha = tk.StringVar(value=config_atual.get("preferencia_notificacao", "Ambos"))
    var_parar = tk.BooleanVar(value=config_atual.get("parar_automatica", False))
    var_tipo_hw = tk.StringVar(value=config_atual.get("tipo_conexao", "BambuMQTT"))

    btn_vincular = btn_testar = entry_token = entry_id = entry_rem = entry_sen = entry_des = None
    ent_b_ip = ent_b_code = ent_b_ser = ent_s_port = ent_s_gcode = None

    def vincular_telegram():
        token = entry_token.get()
        if not token: 
            messagebox.showwarning("Aviso", "Insira o Token primeiro!"); return
        try:
            r = requests.get(f"https://api.telegram.org/bot{token}/getMe").json()
            if r["ok"]:
                pil_img = qrcode.make(f"https://t.me/{r['result']['username']}").resize((130, 130)).convert("RGB")
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(130, 130))
                label_qr.configure(image=ctk_img, text="")
                label_status_qr.configure(text="✅ Envie uma mensagem ao Bot!", text_color="#28a745")
                def escutar():
                    requests.get(f"https://api.telegram.org/bot{token}/getUpdates?offset=-1")
                    for _ in range(30):
                        time.sleep(2)
                        resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates").json()
                        if resp["ok"] and len(resp["result"]) > 0:
                            novo_id = resp["result"][-1]["message"]["chat"]["id"]
                            entry_id.delete(0, tk.END); entry_id.insert(0, str(novo_id))
                            label_status_qr.configure(text="✅ Vinculado com sucesso!", text_color="#28a745"); return
                threading.Thread(target=escutar, daemon=True).start()
        except: label_status_qr.configure(text="❌ Erro de Token/Rede", text_color="#dc3545")

    def teste_rapido_bambu():
        try:
            client = mqtt.Client(CallbackAPIVersion.VERSION2)
            client.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)
            client.username_pw_set("bblp", ent_b_code.get()) 
            client.connect(ent_b_ip.get(), 8883, 5)          
            messagebox.showinfo("Sucesso", "✅ Conexão estabelecida!\nA impressora respondeu.")
            client.disconnect()
        except Exception as e:
            messagebox.showerror("Falha", f"❌ Sem conexão:\n{e}")

    def atualizar_interface():
        if btn_testar is None: return
        
        esc = var_escolha.get()
        st_tg = "normal" if esc in ["Telegram", "Ambos"] else "disabled"
        st_em = "normal" if esc in ["Email", "Ambos"] else "disabled"
        
        entry_token.configure(state=st_tg); entry_id.configure(state=st_tg); btn_vincular.configure(state=st_tg)
        entry_rem.configure(state=st_em); entry_sen.configure(state=st_em); entry_des.configure(state=st_em)
        
        ativo = var_parar.get()
        tipo = var_tipo_hw.get()
        st_b = "normal" if ativo and tipo == "BambuMQTT" else "disabled"
        st_s = "normal" if ativo and tipo == "Serial" else "disabled"
        
        ent_b_ip.configure(state=st_b); ent_b_code.configure(state=st_b); ent_b_ser.configure(state=st_b); btn_testar.configure(state=st_b)
        ent_s_port.configure(state=st_s); ent_s_gcode.configure(state=st_s)

    def salvar():
        config_atual.update({
            "preferencia_notificacao": var_escolha.get(), "telegram_token": entry_token.get(), "telegram_chat_id": entry_id.get(),
            "email_remetente": entry_rem.get(), "email_senha": entry_sen.get(), "email_destino": entry_des.get(),
            "nome_laboratorio": entry_lab.get(), "parar_automatica": var_parar.get(), "tipo_conexao": var_tipo_hw.get(),
            "bambu_ip": ent_b_ip.get(), "bambu_access_code": ent_b_code.get(), "bambu_serial": ent_b_ser.get(),
            "serial_port": ent_s_port.get(), "serial_gcode": ent_s_gcode.get()
        })
        with open('config.json', 'w') as f: json.dump(config_atual, f, indent=4)
        
        # Truque do Delay: Espera 150ms a animação do botão terminar e depois apaga tudo
        root.after(150, lambda: (root.destroy(), root.quit()))
        
    def fechar_programa():
        # Se for para fechar o programa todo, não precisa de delay
        root.destroy()
        os._exit(0)
        
    def voltar():
        # O mesmo truque do delay para o botão voltar não dar erro de animação
        root.after(150, lambda: (root.destroy(), root.quit()))

    root.protocol("WM_DELETE_WINDOW", voltar)

    ctk.CTkLabel(root, text="⚙️ Configurações do Sistema", font=("Roboto", 24, "bold")).pack(pady=(15, 10))
    
    f_nome = ctk.CTkFrame(root, fg_color="transparent")
    f_nome.pack(fill="x", padx=40, pady=(0, 10))
    ctk.CTkLabel(f_nome, text="Nome do Equipamento:", font=("Roboto", 14, "bold")).pack(side="left", padx=(0,10))
    entry_lab = ctk.CTkEntry(f_nome, width=300)
    entry_lab.insert(0, config_atual.get("nome_laboratorio", ""))
    entry_lab.pack(side="left", fill="x", expand=True)

    tabview = ctk.CTkTabview(root, width=680, height=450)
    tabview.pack(padx=20, pady=5, fill="both", expand=True)
    
    tab_notif = tabview.add("📱 Notificações")
    tab_hard = tabview.add("🖨️ Hardware & Controle")

    # ABA 1: NOTIFICAÇÕES
    f_rad = ctk.CTkFrame(tab_notif, fg_color="transparent")
    f_rad.pack(pady=10)
    ctk.CTkLabel(f_rad, text="Ativar alertas via:", font=("Roboto", 14)).pack(side="left", padx=15)
    for t, v in [("Telegram", "Telegram"), ("E-mail", "Email"), ("Ambos", "Ambos")]:
        ctk.CTkRadioButton(f_rad, text=t, variable=var_escolha, value=v, command=atualizar_interface).pack(side="left", padx=15)

    f_split = ctk.CTkFrame(tab_notif, fg_color="transparent")
    f_split.pack(fill="both", expand=True, padx=10, pady=5)
    
    col_esq = ctk.CTkFrame(f_split, fg_color="transparent")
    col_esq.pack(side="left", fill="both", expand=True, padx=(0, 10))
    
    col_dir = ctk.CTkFrame(f_split, width=180, fg_color="#2b2b2b", corner_radius=10)
    col_dir.pack(side="right", fill="y", padx=(10, 0))

    ctk.CTkLabel(col_esq, text="Configuração do Telegram", font=("Roboto", 16, "bold"), text_color="#0088cc").pack(anchor="w", pady=(5, 5))
    f_tk = ctk.CTkFrame(col_esq, fg_color="transparent")
    f_tk.pack(fill="x", pady=2)
    ctk.CTkLabel(f_tk, text="Token do Bot:").pack(side="left", padx=(0, 5))
    ctk.CTkButton(f_tk, text="❓ Ajuda", command=guia_telegram, width=60, height=20, fg_color="transparent", border_width=1).pack(side="right")
    entry_token = ctk.CTkEntry(col_esq, placeholder_text="Cole o token aqui")
    entry_token.insert(0, config_atual.get("telegram_token", ""))
    entry_token.pack(fill="x", pady=(0, 10))

    f_id = ctk.CTkFrame(col_esq, fg_color="transparent")
    f_id.pack(fill="x", pady=2)
    ctk.CTkLabel(f_id, text="Chat ID:").pack(side="left", padx=(0, 5))
    entry_id = ctk.CTkEntry(col_esq)
    entry_id.insert(0, config_atual.get("telegram_chat_id", ""))
    entry_id.pack(fill="x", pady=(0, 20))

    ctk.CTkLabel(col_dir, text="Vincular Conta", font=("Roboto", 14, "bold")).pack(pady=(10, 5))
    btn_vincular = ctk.CTkButton(col_dir, text="📷 Gerar QR Code", command=vincular_telegram, width=140)
    btn_vincular.pack(pady=5)
    label_qr = ctk.CTkLabel(col_dir, text="(QR Code Aqui)", text_color="gray", width=130, height=130)
    label_qr.pack(pady=5)
    label_status_qr = ctk.CTkLabel(col_dir, text="", font=("Roboto", 12))
    label_status_qr.pack()

    ctk.CTkFrame(col_esq, height=2, fg_color="#444444").pack(fill="x", pady=10)

    ctk.CTkLabel(col_esq, text="Configuração de E-mail (Gmail)", font=("Roboto", 16, "bold"), text_color="#4285F4").pack(anchor="w", pady=(5, 5))
    f_em_row = ctk.CTkFrame(col_esq, fg_color="transparent")
    f_em_row.pack(fill="x")
    
    f_rem = ctk.CTkFrame(f_em_row, fg_color="transparent")
    f_rem.pack(side="left", fill="x", expand=True, padx=(0, 5))
    ctk.CTkLabel(f_rem, text="Remetente:").pack(anchor="w")
    entry_rem = ctk.CTkEntry(f_rem, placeholder_text="seuemail@gmail.com")
    entry_rem.insert(0, config_atual.get("email_remetente", ""))
    entry_rem.pack(fill="x")
    
    f_sen = ctk.CTkFrame(f_em_row, fg_color="transparent")
    f_sen.pack(side="left", fill="x", expand=True, padx=(5, 0))
    f_sen_lbl = ctk.CTkFrame(f_sen, fg_color="transparent")
    f_sen_lbl.pack(fill="x")
    ctk.CTkLabel(f_sen_lbl, text="Senha de App:").pack(side="left")
    ctk.CTkButton(f_sen_lbl, text="🔑 Ajuda", command=guia_email, width=60, height=20, fg_color="transparent", border_width=1).pack(side="right")
    entry_sen = ctk.CTkEntry(f_sen, show="*")
    entry_sen.insert(0, config_atual.get("email_senha", ""))
    entry_sen.pack(fill="x")

    ctk.CTkLabel(col_esq, text="Destino (Onde receber o alerta):").pack(anchor="w", pady=(10, 0))
    entry_des = ctk.CTkEntry(col_esq)
    entry_des.insert(0, config_atual.get("email_destino", ""))
    entry_des.pack(fill="x")

    # ABA 2: HARDWARE E CONTROLE
    f_hard_top = ctk.CTkFrame(tab_hard, fg_color="transparent")
    f_hard_top.pack(fill="x", padx=20, pady=15)
    ctk.CTkCheckBox(f_hard_top, text="⚠️ Ativar Parada Automática (Desligar se achar erro)", 
                    variable=var_parar, command=atualizar_interface, font=("Roboto", 15, "bold"), text_color="#f39c12").pack(anchor="w")

    f_bambu = ctk.CTkFrame(tab_hard, fg_color="#2b2b2b", corner_radius=10)
    f_bambu.pack(fill="x", padx=20, pady=10)
    ctk.CTkRadioButton(f_bambu, text="Rede IoT (Bambu Lab MQTT)", variable=var_tipo_hw, value="BambuMQTT", command=atualizar_interface, font=("Roboto", 15)).grid(row=0, column=0, columnspan=4, sticky="w", padx=15, pady=(15, 10))
    ctk.CTkLabel(f_bambu, text="IP:").grid(row=1, column=0, sticky="e", padx=(15, 5), pady=5)
    ent_b_ip = ctk.CTkEntry(f_bambu, width=130)
    ent_b_ip.insert(0, config_atual.get("bambu_ip", ""))
    ent_b_ip.grid(row=1, column=1, sticky="w", pady=5)
    ctk.CTkLabel(f_bambu, text="PIN/Code:").grid(row=1, column=2, sticky="e", padx=(20, 5), pady=5)
    ent_b_code = ctk.CTkEntry(f_bambu, width=110, show="*")
    ent_b_code.insert(0, config_atual.get("bambu_access_code", ""))
    ent_b_code.grid(row=1, column=3, sticky="w", pady=5)
    btn_testar = ctk.CTkButton(f_bambu, text="⚡ Testar Conexão", command=teste_rapido_bambu, width=120, fg_color="#d35400", hover_color="#e67e22")
    btn_testar.grid(row=1, column=4, padx=(20, 15), pady=5)
    ctk.CTkLabel(f_bambu, text="Serial Number:").grid(row=2, column=0, sticky="e", padx=(15, 5), pady=(5, 15))
    ent_b_ser = ctk.CTkEntry(f_bambu, width=280)
    ent_b_ser.insert(0, config_atual.get("bambu_serial", ""))
    ent_b_ser.grid(row=2, column=1, columnspan=4, sticky="w", pady=(5, 15))

    f_serial = ctk.CTkFrame(tab_hard, fg_color="#2b2b2b", corner_radius=10)
    f_serial.pack(fill="x", padx=20, pady=10)
    ctk.CTkRadioButton(f_serial, text="Serial Clássico (Cabo USB / Marlin / Ender)", variable=var_tipo_hw, value="Serial", command=atualizar_interface, font=("Roboto", 15)).grid(row=0, column=0, columnspan=4, sticky="w", padx=15, pady=(15, 10))
    ctk.CTkLabel(f_serial, text="Porta (ex: COM3):").grid(row=1, column=0, sticky="e", padx=(15, 5), pady=(5, 15))
    ent_s_port = ctk.CTkEntry(f_serial, width=100)
    ent_s_port.insert(0, config_atual.get("serial_port", ""))
    ent_s_port.grid(row=1, column=1, sticky="w", pady=(5, 15))
    ctk.CTkLabel(f_serial, text="Comando G-Code:").grid(row=1, column=2, sticky="e", padx=(30, 5), pady=(5, 15))
    ent_s_gcode = ctk.CTkEntry(f_serial, width=100)
    ent_s_gcode.insert(0, config_atual.get("serial_gcode", "M112"))
    ent_s_gcode.grid(row=1, column=3, sticky="w", pady=(5, 15))

    f_botoes = ctk.CTkFrame(root, fg_color="transparent")
    f_botoes.pack(pady=(5, 15))
    ctk.CTkButton(f_botoes, text="💾 SALVAR E INICIAR", command=salvar, fg_color="#28a745", hover_color="#218838", font=("Roboto", 14, "bold"), width=160, height=45).pack(side="left", padx=10)
    ctk.CTkButton(f_botoes, text="⬅️ VOLTAR", command=voltar, fg_color="#555555", hover_color="#333333", font=("Roboto", 14, "bold"), width=140, height=45).pack(side="left", padx=10)
    ctk.CTkButton(f_botoes, text="❌ ENCERRAR SISTEMA", command=fechar_programa, fg_color="#dc3545", hover_color="#c82333", font=("Roboto", 14, "bold"), width=160, height=45).pack(side="left", padx=10)
    
    atualizar_interface()
    root.mainloop()

def executar_kill_switch(config):
    if not config.get("parar_automatica"): return
    
    if config["tipo_conexao"] == "BambuMQTT":
        try:
            client = mqtt.Client(CallbackAPIVersion.VERSION2)
            client.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)
            client.username_pw_set("bblp", config["bambu_access_code"])
            client.connect(config["bambu_ip"], 8883, 60)
            payload = {"print": {"sequence_id": "1", "command": "pause", "param": ""}}
            client.publish(f"device/{config['bambu_serial']}/request", json.dumps(payload), qos=1)
            print("🛑 Comando MQTT de Pausa enviado!")
            client.disconnect()
        except Exception as e: print(f"Erro MQTT: {e}")
        
    elif config["tipo_conexao"] == "Serial":
        try:
            with serial.Serial(config["serial_port"], 115200, timeout=1) as ser:
                ser.write(str.encode(f"{config['serial_gcode']}\r\n"))
                print(f"🛑 G-Code {config['serial_gcode']} enviado!")
        except Exception as e: print(f"Erro Serial: {e}")

def disparar_alertas_background(tipo, frame, config):
    if not os.path.exists('capturas'): os.makedirs('capturas')
    horario = datetime.now().strftime('%H:%M:%S')
    caminho = os.path.join('capturas', f"alerta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
    cv2.imwrite(caminho, frame)
    texto = f"⚠️ FALHA: {tipo} no {config['nome_laboratorio']} às {horario}"
    registrar_log_csv(tipo, config['nome_laboratorio'])
    
    executar_kill_switch(config)
    
    pref = config.get("preferencia_notificacao", "Ambos")
    if pref in ["Telegram", "Ambos"]:
        try:
            url = f"https://api.telegram.org/bot{config['telegram_token']}"
            requests.post(f"{url}/sendMessage", data={'chat_id': config['telegram_chat_id'], 'text': texto}, timeout=10)
            with open(caminho, 'rb') as f: requests.post(f"{url}/sendPhoto", data={'chat_id': config['telegram_chat_id']}, files={'photo': f}, timeout=10)
        except: pass
    if pref in ["Email", "Ambos"]:
        try:
            msg = MIMEMultipart(); msg['From'] = config["email_remetente"]; msg['To'] = config["email_destino"]; msg['Subject'] = texto
            with open(caminho, 'rb') as f: msg.attach(MIMEImage(f.read(), name="falha.jpg"))
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as s:
                s.starttls(); s.login(config["email_remetente"], config["email_senha"]); s.send_message(msg)
        except: pass


# --- LOOP PRINCIPAL E INICIALIZAÇÃO ---
config = carregar_configuracoes()
if not config.get("telegram_token") and not config.get("email_remetente"):
    abrir_janela_setup(config); config = carregar_configuracoes()

print("\n🧠 Carregando motor de Inteligência Artificial YOLO... (Isso pode levar alguns segundos)")
model = YOLO("models/best.pt")
print("✅ IA carregada com sucesso!")

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|tls_verify;0|fflags;nobuffer|flags;low_delay|stimeout;5000000"

ip_impressora = config.get("bambu_ip", "")
codigo_acesso = config.get("bambu_access_code", "")
url_camera = f"rtsps://bblp:{codigo_acesso}@{ip_impressora}:322/streaming/live/1"

print(f"🔄 Solicitando acesso seguro à câmara da impressora no IP {ip_impressora}...")
cap = CameraThread(url_camera)

while not cap.isOpened():
    print("❌ Erro: Não foi possível conectar. A impressora está ligada e o IP está correto?")
    print("Abrindo tela de Setup para correção...")
    
    abrir_janela_setup(config)
    config = carregar_configuracoes() 
    ip_impressora = config.get("bambu_ip", "")
    codigo_acesso = config.get("bambu_access_code", "")
    url_camera = f"rtsps://bblp:{codigo_acesso}@{ip_impressora}:322/streaming/live/1"
    
    print(f"🔄 Tentando conectar novamente no IP {ip_impressora}...")
    cap = CameraThread(url_camera) 

classNames = ['Blobbing', 'Cracks', 'Over Extrusion', 'Spaghetti', 'Stringing', 'Under Extrusion']
contador, confirmado = 0, False
falhas_rede = 0

ctk.set_appearance_mode("dark")
app = ctk.CTk()
app.title(f"Monitor LabInd - {config.get('nome_laboratorio', 'Equipamento')}")
app.geometry("1000x650")

comando_usuario = None
def acao_setup():
    global comando_usuario; comando_usuario = "setup"
def acao_sair():
    global comando_usuario; comando_usuario = "sair"
app.protocol("WM_DELETE_WINDOW", acao_sair) 

frame_menu = ctk.CTkFrame(app, width=280, corner_radius=0, fg_color="#212121")
frame_menu.pack(side="left", fill="y")
frame_video = ctk.CTkFrame(app, fg_color="transparent")
frame_video.pack(side="right", fill="both", expand=True, padx=10, pady=10)

ctk.CTkLabel(frame_menu, text="⚙️ Painel de Controle", font=("Roboto", 20, "bold")).pack(pady=(30, 20))
lbl_status = ctk.CTkLabel(frame_menu, text="Status: Iniciando...", font=("Roboto", 18, "bold"), text_color="#17a2b8")
lbl_status.pack(pady=(10, 5))
lbl_falha = ctk.CTkLabel(frame_menu, text="Falhas: 0/30", font=("Roboto", 16))
lbl_falha.pack(pady=5)
lbl_rede = ctk.CTkLabel(frame_menu, text="Wi-Fi: Conectando...", font=("Roboto", 14), text_color="gray")
lbl_rede.pack(pady=(5, 30))

ctk.CTkButton(frame_menu, text="⚙️ Configurações", command=acao_setup, fg_color="#f39c12", hover_color="#e67e22", height=45, font=("Roboto", 15, "bold")).pack(side="bottom", pady=(10, 20), padx=20, fill="x")
ctk.CTkButton(frame_menu, text="❌ Encerrar", command=acao_sair, fg_color="#dc3545", hover_color="#c82333", height=45, font=("Roboto", 15, "bold")).pack(side="bottom", pady=0, padx=20, fill="x")

lbl_camera = ctk.CTkLabel(frame_video, text="")
lbl_camera.pack(fill="both", expand=True)

while True:
    try:
        if comando_usuario == "setup":
            comando_usuario = None
            app.withdraw() 
            cap.release()
            
            abrir_janela_setup(config) 
            config = carregar_configuracoes() 
            ip_impressora = config.get("bambu_ip", "")
            codigo_acesso = config.get("bambu_access_code", "")
            url_camera = f"rtsps://bblp:{codigo_acesso}@{ip_impressora}:322/streaming/live/1"
            cap = CameraThread(url_camera) 
            
            app.deiconify() 
            continue
            
        elif comando_usuario == "sair":
            break

        ret, img = cap.read()
        
        if not ret:
            falhas_rede += 1
            lbl_rede.configure(text=f"Wi-Fi: Engasgando ({falhas_rede}/30)", text_color="#f39c12")
            app.update()
            if falhas_rede > 30:
                lbl_rede.configure(text="Wi-Fi: Reconectando...", text_color="#dc3545")
                app.update()
                cap.release()
                cap = CameraThread(url_camera)
                falhas_rede = 0
            continue 
            
        falhas_rede = 0 
        lbl_rede.configure(text="Wi-Fi: Estável", text_color="#28a745")

        altura, largura, _ = img.shape
        results = model(img, stream=True, conf=0.5)
        detectou, classe = False, ""
        
        for r in results:
            for box in r.boxes:
                detectou = True
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
                classe = classNames[int(box.cls[0])]
                cv2.rectangle(img, (x1, y1-25), (x1 + len(classe)*12, y1), (0, 0, 255), -1)
                cv2.putText(img, f'{classe}', (x1+5, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        limite = config.get("limite_persistencia", 30)
        if detectou: contador = min(limite, contador + 1)
        else: contador = max(0, contador - 1)

        if contador >= limite and not confirmado:
            threading.Thread(target=disparar_alertas_background, args=(classe, img.copy(), config)).start()
            confirmado = True
        elif contador == 0: 
            confirmado = False

        if detectou:
            lbl_status.configure(text=f"ALERTA: {classe}", text_color="#dc3545")
        else:
            lbl_status.configure(text="Status: Operando Normal", text_color="#28a745")
            
        lbl_falha.configure(text=f"Falhas: {contador}/{limite}")

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_ctk = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(largura, altura))
        lbl_camera.configure(image=img_ctk)
        
        app.update()
    except tk.TclError:
        break

cap.release()
app.destroy()