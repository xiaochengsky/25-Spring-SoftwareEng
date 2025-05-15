import importlib.util
import inspect
import os

from TxDefi.Abstractions.AbstractTradingStrategy import AbstractTradingStrategy

def find_classes_with_parent_class(directory, parent_class)->list[str]:
    """Scans a directory for Python files containing a class inheriting from an abstract class."""
    py_files = [f for f in os.listdir(directory) if f.endswith(".py")]
    matching_modules : dict[str, any] = {}

    for py_file in py_files:
        module_name = py_file[:-3]  # Remove '.py'
        module_path = os.path.join(directory, py_file)

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)  # Import the module
        except Exception as e:
            print(f"Skipping {py_file} due to import error: {e}")
            continue

        # Inspect module for classes that inherit from the abstract base class
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, parent_class) and cls is not parent_class:
                matching_modules[cls.__name__] = module
                break  # Stop checking once we find a match

    return matching_modules

#directory = "Strategies/Examples"  # Change this to your directory path
#found_modules = find_classes_with_parent_class(directory, AbstractTradingStrategy)
#
#for class_name in found_modules:
#    MyClass = getattr(found_modules[class_name], class_name)
#    print(MyClass.name)
#print("Python files containing a class inheriting from MyAbstractBase:", found_modules)
