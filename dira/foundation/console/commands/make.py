from dira.main import cli
import click
import os
import subprocess
import inflection

@cli.command("make.controller")
@click.argument('name')
@click.argument('class_name', required=False)
def generate_controller_file(name, class_name=None):
    class_name = class_name or inflection.camelize(name)
    file_name = inflection.underscore(name)
    # Определяем путь к директории для контроллеров
    controllers_dir = os.path.join("app", "http", "controllers")
    
    # Создаем директорию для контроллера, если она не существует
    if not os.path.exists(controllers_dir):
        os.makedirs(controllers_dir)
    
    # Формируем полный путь к файлу контроллера
    controller_file = os.path.join(controllers_dir, f"{file_name}.py")
    
    # Генерируем содержимое файла контроллера
    content = f"""
class {class_name}():
    pass
"""
    
    # Записываем содержимое в файл
    with open(controller_file, "w") as file:
        file.write(content)
    
    print(f"Контроллер {class_name} успешно создан по пути {controller_file}")

@cli.command("make.provider")
@click.argument('name')
def generate_provider_file(name):
    class_name = inflection.camelize(name)
    file_name = inflection.underscore(name)
    # Определяем путь к директории для контроллеров
    dir_path = os.path.join("app", "http", "provider")
    
    # Создаем директорию для контроллера, если она не существует
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    # Формируем полный путь к файлу контроллера
    file_path = os.path.join(dir_path, f"{file_name}.py")
    
    # Генерируем содержимое файла контроллера
    content = f"""
                class {class_name}():
                    pass
                """
    
    # Записываем содержимое в файл
    with open(file_path, "w") as file:
        file.write(content)
    
    print(f"Провайдер {class_name} успешно создан по пути {file_path}")


@cli.command("install")
def package_install():
    packages_dir = "packages"  # Путь к папке с пакетами
    for package in os.listdir(packages_dir):
        package_path = os.path.join(packages_dir, package)
        if os.path.isdir(package_path):
            setup_path = os.path.join(package_path, "setup.py")
            pyproject_path = os.path.join(package_path, "pyproject.toml")
            if os.path.exists(setup_path) or os.path.exists(pyproject_path):
                # Запуск скрипта setup.py для установки пакета
                subprocess.run(["pip", "install", package_path])
                print(f"Package {package} installed successfully.")
            else:
                print(f"Package {package} does not contain setup.py.")
