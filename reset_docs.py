import os
import shutil

class DirectoryManager:
    def __init__(self, dir_name="documentos"):
        self.dir_name = dir_name
        self.current_path = os.getcwd()
        self.path_dir = os.path.join(self.current_path, self.dir_name)

    def exist_dir_checker(self):
        return os.path.exists(self.path_dir) and os.path.isdir(self.path_dir)

    def dir_erase(self):
        if self.exist_dir_checker():
            try:
                shutil.rmtree(self.path_dir)
                print(f"A pasta '{self.dir_name}' foi apagada com sucesso.")
            except Exception as e:
                print(f"Ocorreu um erro ao tentar apagar a pasta: {e}")
        else:
            print(f"A pasta '{self.dir_name}' não foi encontrada no diretório atual.")

