# Imagen base de Python
FROM python:3.10

# Directorio de trabajo del contenedor
WORKDIR /app

# Copiar todos los archivos al contenedor
COPY . /app

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Exponer puerto de Flask
EXPOSE 5000

# Comando de inicio
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

