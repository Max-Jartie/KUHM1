import unittest
from emulator import ShellEmulator
import os
import json
import shutil
import csv

class TestShellEmulator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Создаём копию vfs.zip для тестирования, чтобы не повредить основной архив
        shutil.copyfile('vfs.zip', 'vfs_test.zip')
        # Создаём config_test.json
        with open('config_test.json', 'w', encoding='utf-8') as f:
            json.dump({
                "vfs_path": "vfs_test.zip",
                "log_path": "log.csv",
                "startup_script": "startup.sh"
            }, f, indent=4)

    @classmethod
    def tearDownClass(cls):
        # Удаляем тестовый архив после всех тестов
        if os.path.exists('vfs_test.zip'):
            os.remove('vfs_test.zip')
        if os.path.exists('config_test.json'):
            os.remove('config_test.json')
        # Удаляем лог-файл
        if os.path.exists('log.csv'):
            os.remove('log.csv')

    def setUp(self):
        # Используем тестовый архив
        self.emulator = ShellEmulator('config_test.json')

    def tearDown(self):
        # Очистка после каждого теста
        if hasattr(self, 'emulator') and self.emulator.vfs_path_extracted:
            self.emulator.cleanup()

    def test_ls_command_root(self):
        """Проверка вывода команды ls в корневой директории"""
        self.emulator.current_path = '/'  # Reset the current directory to '/'
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('ls')
        __builtins__.print = original_print

        expected = {'home/', 'startup.sh', 'file1.txt'}
        self.assertEqual(set(captured_output), expected)



    def test_cd_command_success(self):
        """Проверка успешного перехода в существующую директорию"""
        self.emulator.execute_command('cd home/user')
        self.assertEqual(self.emulator.current_path, '/home/user')

    def test_cd_command_failure(self):
        """Проверка перехода в несуществующую директорию"""
        self.emulator.current_path = '/'  # Reset the current directory to '/'
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('cd non_existent_dir')
        __builtins__.print = original_print
        self.assertIn('no such file or directory', captured_output[0])

    def test_cat_command_success(self):
        """Проверка вывода содержимого файла"""
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('cat file1.txt')
        __builtins__.print = original_print
        self.assertIn('Hello, world!', captured_output[0])

    def test_cat_command_failure(self):
        """Проверка ошибки при выводе несуществующего файла"""
        captured_output = []
        def mock_print(s):
            captured_output.append(s)
        original_print = __builtins__.print
        __builtins__.print = mock_print
        self.emulator.execute_command('cat non_existent_file.txt')
        __builtins__.print = original_print
        self.assertIn('No such file or directory', captured_output[0])

if __name__ == '__main__':
    unittest.main()