import cv2
import numpy as np

def testar_filtro():
    # Mude o '0' para a URL da sua câmera (ex: "rtsp://...") se quiser testar direto nela
    # Ou deixe 0 para testar com a webcam do seu notebook/PC
    cap = cv2.VideoCapture(0)

    print("Iniciando teste de visão. Pressione a tecla 'Q' para sair.")

    # Cria o objeto CLAHE (Você pode brincar com o clipLimit aqui para ver a diferença)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Erro ao capturar a câmera.")
            break

        # Redimensiona para não estourar o tamanho do seu monitor no modo lado a lado
        frame = cv2.resize(frame, (640, 480))

        # --- A MÁGICA DO CLAHE COLORIDO ---
        # 1. Converte BGR (padrão) para o espaço LAB (Luminosidade, cor A, cor B)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # 2. Separa os canais
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # 3. Aplica o CLAHE APENAS no canal 'L' (Luminosidade)
        cl = clahe.apply(l_channel)
        
        # 4. Junta o canal 'L' modificado com as cores originais 'A' e 'B'
        merged = cv2.merge((cl, a_channel, b_channel))
        
        # 5. Converte de volta para BGR para podermos ver na tela
        frame_clahe = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        # -----------------------------------

        # Adiciona textos nas imagens para identificação
        cv2.putText(frame, "ORIGINAL", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame_clahe, "CLAHE COLORIDO (O Holofote)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Junta as duas imagens lado a lado
        comparacao = np.hstack((frame, frame_clahe))

        # Exibe a janela
        cv2.imshow("Teste do Filtro", comparacao)

        # Sai ao apertar a tecla 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    testar_filtro()
