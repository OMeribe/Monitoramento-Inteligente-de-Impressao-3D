from ultralytics import YOLO
from roboflow import Roboflow

def avaliar_forca_do_modelo():
    print("1. Conectando ao Roboflow e baixando o gabarito (Validation Set)...")
    # O script usa suas credenciais para puxar as imagens originais de teste
    rf = Roboflow(api_key="lKlzPAGShtufNtaQHPbt")
    project = rf.workspace("sylucauc").project("3d-printing-failure-detection")
    version = project.version(3)
    dataset = version.download("yolov11")

    print("\n2. Carregando o seu cérebro atual (models/best.pt)...")
    # Puxa o modelo que o seu sistema principal está usando agora
    model = YOLO("models/best.pt")

    print("\n3. Iniciando a prova final (Isso pode levar um minutinho)...")
    # O comando val() testa a IA contra as imagens que ela nunca viu no treino
    metrics = model.val(data=f"{dataset.location}/data.yaml", split='val', plots=True)

    print("\n" + "="*55)
    print("📊 RESULTADOS DA FORÇA DO MODELO (MÉTRICAS OFICIAIS)")
    print("="*55)
    
    # Extraindo as médias das métricas
    mp = metrics.box.mp    # Mean Precision
    mr = metrics.box.mr    # Mean Recall
    map50 = metrics.box.map50 # mAP@50
    map95 = metrics.box.map   # mAP@50-95

    print(f"🔹 Precisão (Precision): {mp:.2%}")
    print(f"🔹 Revocação (Recall):   {mr:.2%}")
    print(f"🔹 mAP@50:               {map50:.2%}")
    print(f"🔹 mAP@50-95:            {map95:.2%}")
    print("="*55)
    
    print("\n💡 COMO INTERPRETAR ESSES NÚMEROS NO SEU TCC:")
    print("- Precisão: Quando a IA diz 'É Espaguete!', qual a chance de ela estar certa?")
    print("  (Se for muito baixa, ela sofre de Falso Positivo. Chuta muito).")
    
    print("- Revocação: De todos os erros reais que existiam nas fotos, quantos ela achou?")
    print("  (Se for muito baixa, ela sofre de Falso Negativo. É 'cega' para erros sutis).")
    
    print("- mAP@50: É a 'Nota do Boletim'. Acima de 60% é funcional. Acima de 80% é excelente.")
    
    print(f"\n✅ Gráficos extras foram salvos na pasta: {metrics.save_dir}")

if __name__ == "__main__":
    avaliar_forca_do_modelo()