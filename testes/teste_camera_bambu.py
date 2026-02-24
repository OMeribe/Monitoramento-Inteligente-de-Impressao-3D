import cv2
import os

# 1. Ignorar verificação de certificado SSL (Crucial para a Bambu Lab)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|tls_verify;0"

# 2. Dados da Impressora (Preencha aqui para o teste)
IP_IMPRESSORA = "192.168.100.104" #Confirme se é esse IP mesmo
ACCESS_CODE = "49888f6a"   # Código PIN de 8 dígitos

print(f"🔄 Tentando conectar à Bambu Lab no IP {IP_IMPRESSORA}...")
url_camera = f"rtsps://bblp:{ACCESS_CODE}@{IP_IMPRESSORA}:322/streaming/live/1"

# 3. Iniciar Captura
cap = cv2.VideoCapture(url_camera)

if not cap.isOpened():
    print("❌ Erro: Não consegui conectar.")
    print("Verifique: 1) O IP está correto? 2) O Access Code está correto? 3) O PC e a impressora estão no mesmo Wi-Fi?")
else:
    print("✅ Conectado com sucesso! Abrindo janela de vídeo...")
    print("Pressione a tecla 'Q' na janela do vídeo para encerrar o teste.")

# 4. Loop de exibição
while True:
    ret, frame = cap.read()
    
    if not ret:
        print("⚠️ Sinal de vídeo perdido.")
        break
    
    # Mostra a imagem na tela
    cv2.imshow("Teste - Camera Bambu Lab", frame)
    
    # Sai se o usuário apertar 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Encerra tudo
cap.release()
cv2.destroyAllWindows()