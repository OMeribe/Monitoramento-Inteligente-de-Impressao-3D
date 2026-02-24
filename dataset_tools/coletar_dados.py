import cv2
import os
import time

# 1. Configurações Iniciais
SAVE_PATH = "data/treino"
classes = ["sucesso", "falha"]

# Cria as pastas se elas não existirem
for cls in classes:
    os.makedirs(os.path.join(SAVE_PATH, cls), exist_ok=True)

cap = cv2.VideoCapture(0)

print("--- COLETOR DE DATASET ATIVADO ---")
print("Comandos:")
print("  Pressione 's' -> Salva na pasta SUCESSO")
print("  Pressione 'f' -> Salva na pasta FALHA")
print("  Pressione 'q' -> Sair")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Exibe instruções na tela para facilitar
    cv2.putText(frame, "S: Sucesso | F: Falha | Q: Sair", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    cv2.imshow('Coletor de Dados TCC', frame)
    
    key = cv2.waitKey(1) & 0xFF

    # Lógica de salvamento
    if key == ord('s'):
        filename = f"sucesso_{int(time.time())}.jpg"
        cv2.imwrite(os.path.join(SAVE_PATH, "sucesso", filename), frame)
        print(f"Foto salva em SUCESSO: {filename}")
        
    elif key == ord('f'):
        filename = f"falha_{int(time.time())}.jpg"
        cv2.imwrite(os.path.join(SAVE_PATH, "falha", filename), frame)
        print(f"Foto salva em FALHA: {filename}")

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()