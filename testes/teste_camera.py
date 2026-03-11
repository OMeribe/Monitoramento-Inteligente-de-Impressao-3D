import cv2

cap = cv2.VideoCapture(0) 

if not cap.isOpened():
    print("Erro: Não foi possível acessar a câmera.")
else:
    print("Câmera acessada com sucesso! Pressione 'q' para fechar.")

while True:
    ret, frame = cap.read()
    
    if not ret:
        print("Erro ao receber frame. Saindo...")
        break

    cv2.imshow('Teste TCC - Pressione Q para sair', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()