from ultralytics import YOLO

def main():
    # 1. Carrega um modelo YOLO pré-treinado (Nano - mais rápido)
    model = YOLO('yolov8n.pt')

    # 2. Inicia o treinamento
    # 'data' aponta para o seu arquivo .yaml do Roboflow
    # 'epochs' é quantas vezes a IA vai ler o dataset inteiro
    # 'imgsz' é o tamanho da imagem (640 é o padrão)
    model.train(
    data='3d-printing-failure-1/data.yaml', # Este é o caminho real na sua pasta
    epochs=50, 
    imgsz=640, 
    device='cpu', 
    project='tcc_3d_printing',
    name='experimento_01'
)

if __name__ == '__main__':
    main()