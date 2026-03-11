from roboflow import Roboflow

# Substitua pela sua chave que o site vai te dar
rf = Roboflow(api_key="")
project = rf.workspace("3d-printing-failure").project("3d-printing-failure")
version = project.version(1) # Ou a versão mais recente
dataset = version.download("yolov8")



                