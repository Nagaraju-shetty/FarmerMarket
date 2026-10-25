
import agmarknet

print("AGMARKNET package imported successfully!")
print("Package location:", agmarknet.__file__)
print("Available package functions:")
print([name for name in dir(agmarknet) if not name.startswith("_")])
