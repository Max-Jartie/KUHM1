import os
import zipfile
import json
import sys
from datetime import datetime
import shutil
import tempfile
import csv  # Добавлен импорт модуля csv

class ShellEmulator:
    def __init__(self, config_path):
        self.load_config(config_path)
        self.load_vfs()
        self.current_path = '/'
        self.log = []
        self.run_startup_script()

    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        self.vfs_path = config['vfs_path']
        self.log_path = config['log_path']
        self.startup_script = config['startup_script']

    def load_vfs(self):
        if not os.path.isfile(self.vfs_path) or not zipfile.is_zipfile(self.vfs_path):
            print("Invalid VFS archive.")
            sys.exit(1)
        # Создаём временную директорию для распаковки
        self.temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(self.vfs_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        self.vfs_path_extracted = self.temp_dir
        self.read_vfs()

    def read_vfs(self):
        # Обновляем список файлов и директорий
        self.files = []
        for root, dirs, files in os.walk(self.vfs_path_extracted):
            for dir in dirs:
                full_dir_path = os.path.join(root, dir)
                relative_path = os.path.relpath(full_dir_path, self.vfs_path_extracted)
                self.files.append('/' + relative_path.replace(os.sep, '/') + '/')
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, self.vfs_path_extracted)
                self.files.append('/' + relative_path.replace(os.sep, '/'))

    def log_action(self, action):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action
        }
        self.log.append(entry)
        with open(self.log_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=entry.keys())
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow(entry)

    def run_startup_script(self):
        script_full_path = os.path.join(self.vfs_path_extracted, self.startup_script)
        if os.path.isfile(script_full_path):
            with open(script_full_path, 'r') as f:
                commands = f.read().splitlines()
            for cmd in commands:
                self.execute_command(cmd)

    def prompt(self):
        return f"shell@emulator:{self.current_path}$ "

    def list_dir(self, args):
        target_path = self.current_path
        if args:
            target_path = self.normalize_path(args[0])
            if not target_path.endswith('/'):
                target_path += '/'

        if not any(f.startswith(target_path) for f in self.files):
            print(f"ls: cannot access '{target_path}': No such file or directory")
            return

        contents = set()
        for f in self.files:
            if f.startswith(target_path) and f != target_path:
                relative_path = f[len(target_path):].lstrip('/')
                first_part = relative_path.split('/')[0]
                is_directory = any(item == target_path + first_part + '/' for item in self.files)
                if is_directory:
                    contents.add(first_part + '/')
                else:
                    contents.add(first_part)

        for item in sorted(contents):
            print(item)


    def change_dir(self, args):
        if not args:
            return
        new_path = args[0]
        if new_path == "..":
            if self.current_path != '/':
                self.current_path = os.path.dirname(self.current_path.rstrip('/')) or '/'
        else:
            potential_path = self.normalize_path(new_path)
            if not potential_path.endswith('/'):
                potential_path += '/'
            if any(f == potential_path or f.startswith(potential_path) for f in self.files):
                self.current_path = potential_path.rstrip('/')
                if self.current_path == '':
                    self.current_path = '/'
            else:
                print(f"cd: no such file or directory: {new_path}")

    def cat_file(self, args):
        if not args:
            print("cat: missing file operand.")
            return
        file = self.normalize_path(args[0])
        full_file_path = self.get_full_path(file)
        if not os.path.exists(full_file_path):
            print(f"cat: {file}: No such file or directory")
            return
        try:
            with open(full_file_path, 'r') as f:
                print(f.read())
        except Exception as e:
            print(f"cat: error reading '{file}': {e}")

    def echo(self, args):
        if len(args) < 3 or args[-2] != '>':
            print("Usage: echo <text> > <file>")
            return

        # Разделяем текст и файл
        file_path = self.normalize_path(args[-1])  # Путь к файлу — последний аргумент
        text_to_write = ' '.join(args[:-2])        # Текст для записи — всё до '>'

        # Получаем полный путь в VFS
        full_file_path = self.get_full_path(file_path)

        try:
            # Создаем родительские директории, если их нет
            os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
            # Записываем текст в файл
            with open(full_file_path, 'w') as f:
                f.write(text_to_write + '\n')
            print(f"Text written to {file_path}")
        except Exception as e:
            print(f"echo: error writing to {file_path}: {e}")


    def normalize_path(self, path):
        if not path.startswith('/'):
            path = os.path.join(self.current_path, path)
        return os.path.normpath(path).replace('\\', '/')

    def get_full_path(self, path):
        if path.startswith('/'):
            return os.path.join(self.vfs_path_extracted, path.lstrip('/'))
        else:
            return os.path.join(self.vfs_path_extracted, self.current_path.lstrip('/'), path)

    def execute_command(self, command_line):
        if not command_line.strip():
            return
        parts = command_line.strip().split()
        cmd, args = parts[0], parts[1:]
        if cmd == 'ls':
            self.list_dir(args)
        elif cmd == 'cd':
            self.change_dir(args)
        elif cmd == 'cat':
            self.cat_file(args)
        elif cmd == 'echo':
            self.echo(args)
        elif cmd == 'exit':
            self.log_action("exit")
            self.cleanup()
            sys.exit(0)
        else:
            print(f"{cmd}: command not found")
        self.log_action(command_line)

    def cleanup(self):
        # Упакуйте обратно в zip
        if os.path.exists(self.vfs_path_extracted):
            shutil.make_archive("vfs_updated", 'zip', self.vfs_path_extracted)
            shutil.move("vfs_updated.zip", self.vfs_path)
            shutil.rmtree(self.vfs_path_extracted)
            self.vfs_path_extracted = None

    def run(self):
        try:
            while True:
                command = input(self.prompt())
                self.execute_command(command)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting shell.")
            self.log_action("exit")
            self.cleanup()
            sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python emulator.py config.json")
        sys.exit(1)
    emulator = ShellEmulator(sys.argv[1])
    emulator.run()