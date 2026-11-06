PublicAlert - Sistema de Gestión de Reportes Ciudadanos

PublicAlert es una plataforma web desarrollada para facilitar el registro, visualización y gestión de reportes de afectaciones en la vía pública o infraestructura. El sistema permite a los ciudadanos crear reportes con ubicación geográfica y adjuntar evidencia fotográfica, mientras proporciona a los administradores un panel de control dedicado para la moderación, actualización de estados y eliminación de registros.

Tecnologías Utilizadas

El proyecto está construido bajo la siguiente pila tecnológica:

Backend: Python 3, Flask

Base de Datos: SQLite (Desarrollo), SQLAlchemy (ORM)

Frontend: HTML5, CSS3, Jinja2 (Motor de plantillas)

Entorno de Despliegue Objetivo: Render

Instrucciones de Instalación y Ejecución Local

Para ejecutar este proyecto en un entorno de desarrollo local, es necesario contar con Python 3 instalado en su sistema. Siga los pasos descritos a continuación según su sistema operativo.

1. Clonar el repositorio

Abra su terminal o línea de comandos y ejecute la siguiente instrucción para descargar el código fuente:

git clone [URL_DEL_REPOSITORIO]
cd publicalert

2. Creación del entorno virtual

Se requiere el uso de un entorno virtual para aislar las dependencias del proyecto y evitar conflictos con las librerías del sistema.

Para sistemas Windows:
python -m venv venv
venv\Scripts\activate

Para sistemas Linux y macOS:
python3 -m venv venv
source venv/bin/activate

3. Instalación de dependencias

Una vez que el entorno virtual se encuentre activo (se indicará con un prefijo (venv) en su terminal), proceda a instalar las librerías requeridas especificadas en el archivo de configuración:

pip install -r requirements.txt

4. Ejecución del servidor local

Para iniciar la aplicación, ejecute el archivo principal del servidor:

python app.py

El servidor iniciará en modo de desarrollo. Puede acceder a la plataforma abriendo su navegador web y dirigiéndose a la dirección: http://127.0.0.1:5000

Notas de Desarrollo y Despliegue

Control de Versiones: Asegúrese de no alterar el archivo .gitignore. La carpeta venv y el archivo publicalert.db están excluidos del rastreo de Git de manera intencional para evitar conflictos entre los entornos locales de los desarrolladores.

Producción: En el entorno de producción (Render), el sistema instalará las dependencias automáticamente a partir del archivo requirements.txt. El entorno virtual local no debe ser subido al servidor.