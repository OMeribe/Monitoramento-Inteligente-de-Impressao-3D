import cv2
import os

# ==========================================
# 1. COLOQUE OS DADOS DA SUA IMPRESSORA AQUI
# ==========================================
BAMBU_IP = "192.168.100.208"  # Coloque o IP atual
BAMBU_PIN = "49888f6a"    # Coloque o Access Code
# ==========================================

# Configuração rigorosa de rede para a imagem chegar lisa em tempo real
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|tls_verify;0|fflags;nobuffer|flags;low_delay|stimeout;1000000"
)

RTSP_URL = f"rtsps://bblp:{BAMBU_PIN}@{BAMBU_IP}:322/streaming/live/1"
pasta_destino = "fotos_originais"
os.makedirs(pasta_destino, exist_ok=True)

print(f"Conectando a camera da Bambu Lab ({BAMBU_IP})...")
cap = cv2.VideoCapture(RTSP_URL)

if not cap.isOpened():
    print("[ERRO] Nao consegui conectar. Verifique o IP, o PIN e se o PC esta na mesma rede.")
    exit()

print("\n" + "="*35)
print("📸 ESTUDIO DE CAPTURA INICIADO 📸")
print("="*35)
print(" Aperte 'ESPACO' ou 'S' para salvar uma foto.")
print(" Aperte 'Q' para encerrar o programa.")
print("="*35 + "\n")

contador = 1

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    # Mostra a imagem ao vivo
    cv2.imshow("Captura de Dataset - Bambu Lab (Aperte ESPACO para tirar foto)", frame)

    key = cv2.waitKey(1) & 0xFF
    
    # Se apertar 'q', sai do programa
    if key == ord('q'):
        break
        
    # Se apertar 's' ou a Barra de Espaço, salva a foto!
    elif key == ord('s') or key == 32: 
        nome_arquivo = os.path.join(pasta_destino, f"erro_preto_{contador:03d}.jpg")
        cv2.imwrite(nome_arquivo, frame)
        print(f"[+] CLICK! Foto salva: {nome_arquivo}")
        contador += 1
        
        # Faz a tela piscar em branco rapidinho igual uma câmera digital
        tela_branca = frame.copy()
        tela_branca[:] = (255, 255, 255)
        cv2.imshow("Captura de Dataset - Bambu Lab (Aperte ESPACO para tirar foto)", tela_branca)
        cv2.waitKey(50)

cap.release()
cv2.destroyAllWindows()