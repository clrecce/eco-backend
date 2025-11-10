import time

print("--- Iniciando Script Ineficiente ---")
lista = []
for i in range(1000000):
    lista.append(i)

# Abrir un archivo sin 'with' (mala práctica)
f = open("test.txt", "w")


