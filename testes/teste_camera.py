import cv2

# O comando correto é VideoCapture
cap = cv2.VideoCapture(0) 

# Verifica se a câmera abriu corretamente
if not cap.isOpened():
    print("Erro: Não foi possível acessar a câmera.")
else:
    print("Câmera acessada com sucesso! Pressione 'q' para fechar.")

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("Erro ao receber frame. Saindo...")
        break

    # Exibe o frame na tela
    cv2.imshow('Teste TCC - Pressione Q para sair', frame)

    # Sai do loop ao pressionar a tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Libera os recursos
cap.release()
cv2.destroyAllWindows()