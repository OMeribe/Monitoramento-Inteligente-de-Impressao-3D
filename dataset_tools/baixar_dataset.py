from roboflow import Roboflow


rf = Roboflow(api_key="lKlzPAGShtufNtaQHPbt")
project = rf.workspace("sylucauc").project("3d-printing-failure-detection")
version = project.version(3)
dataset = version.download("yolov11")