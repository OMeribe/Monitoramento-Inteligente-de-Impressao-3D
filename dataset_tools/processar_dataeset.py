import cv2
import os

def aplicar_clahe_em_lote(pasta_entrada, pasta_saida):
    # Cria a pasta de saída se ela não existir
    os.makedirs(pasta_saida, exist_ok=True)
    
    # Configura o filtro CLAHE com os parâmetros industriais
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    
    contador = 0
    print(f"Lendo imagens da pasta: '{pasta_entrada}'...\n")
    
    for nome_arquivo in os.listdir(pasta_entrada):
        if nome_arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
            caminho_img = os.path.join(pasta_entrada, nome_arquivo)
            img = cv2.imread(caminho_img)
            
            if img is None:
                print(f"[ERRO] Nao foi possivel ler: {nome_arquivo}")
                continue
                
            # 1. Converte para o espaço de cor LAB
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            
            # 2. Aplica o CLAHE apenas no canal de Luminosidade
            cl = clahe.apply(l_channel)
            
            # 3. Junta os canais e volta para BGR (imagem colorida)
            limg = cv2.merge((cl, a_channel, b_channel))
            img_final = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            
            # 4. Salva a nova imagem
            caminho_salvar = os.path.join(pasta_saida, f"clahe_{nome_arquivo}")
            cv2.imwrite(caminho_salvar, img_final)
            
            contador += 1
            print(f"[OK] Filtro aplicado: clahe_{nome_arquivo}")
            
    print(f"\n[SUCESSO] {contador} imagens processadas e salvas em '{pasta_saida}'.")

if __name__ == "__main__":
    pasta_origem = "fotos_originais"
    pasta_destino = "fotos_processadas"
    
    os.makedirs(pasta_origem, exist_ok=True)
    
    if len(os.listdir(pasta_origem)) == 0:
        print(f"A pasta '{pasta_origem}' esta vazia. Coloque as fotos la primeiro!")
    else:
        aplicar_clahe_em_lote(pasta_origem, pasta_destino)