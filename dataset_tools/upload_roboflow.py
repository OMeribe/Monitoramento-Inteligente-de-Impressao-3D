import os
from roboflow import Roboflow
try:
    from roboflow import Roboflow
except ImportError:
    print("Instalando a biblioteca do Roboflow...")
    os.system("pip install roboflow")
    from roboflow import Roboflow

# ==========================================
# PREENCHA COM OS SEUS DADOS DO ROBOFLOW
# ==========================================
# 1. Pegue sua API Key em: Settings -> Workspace -> Roboflow API
CHAVE_API = "lKlzPAGShtufNtaQHPbt"

# 2. Olhe para a URL do seu projeto no navegador. 
# Exemplo: se for https://app.roboflow.com/udesc-lab/meu-tcc-visao/
# O workspace é "udesc-lab" e o projeto é "meu-tcc-visao"
NOME_WORKSPACE = "meribao"
NOME_PROJETO = "find-spaghetti-and-my-first-project"
# ==========================================

rf = Roboflow(api_key=CHAVE_API)
project = rf.workspace(NOME_WORKSPACE).project(NOME_PROJETO)

pasta_imagens = "fotos_processadas"

print(f"Conectado ao Roboflow! Lendo a pasta '{pasta_imagens}'...\n")

if not os.path.exists(pasta_imagens):
    print(f"[ERRO] A pasta '{pasta_imagens}' nao foi encontrada.")
    exit()

imagens = [f for f in os.listdir(pasta_imagens) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
contador = 0

print(f"Iniciando upload de {len(imagens)} imagens via API...\n")

for nome_img in imagens:
    caminho_completo = os.path.join(pasta_imagens, nome_img)
    try:
        # A mágica acontece aqui: envia direto pro servidor ignorando o navegador
        project.upload(caminho_completo)
        contador += 1
        print(f"[+] Enviada com sucesso ({contador}/{len(imagens)}): {nome_img}")
    except Exception as e:
        print(f"[-] Erro ao enviar {nome_img}: {e}")

print(f"\nUpload finalizado! {contador} imagens injetadas no projeto.")
print("Pode atualizar a página do Roboflow no seu navegador.")