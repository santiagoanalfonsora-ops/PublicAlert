import os
import smtplib
import uuid
import folium
import base64

from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from markupsafe import escape

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort
)

from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)

from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db, Usuario, Reporte, Calificacion, Afectacion,
    CATEGORIAS, ESTADOS, COLORES
)


# ---------- CONFIGURACIÓN ----------
BASE = os.path.abspath(os.path.dirname(__file__))
EXTENSIONES = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)

# --- INICIO DE CONFIGURACIÓN DE BASE DE DATOS ---
# 1. Definimos la ruta local de SQLite por si no estamos en Render
ruta_sqlite_local = "sqlite:///" + os.path.join(BASE, "publicalert.db")

# 2. Obtenemos la URL de Render (DATABASE_URL), si no existe, usa la local
database_url = os.environ.get("DATABASE_URL", ruta_sqlite_local)

# 3. Corregimos el prefijo porque Render entrega postgres:// y SQLAlchemy pide postgresql://
# 3. Corregimos el prefijo para forzar el uso de psycopg2
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "cambiar-en-produccion"),
    SQLALCHEMY_DATABASE_URI=database_url,  # <-- Aquí inyectamos la variable corregida
    UPLOAD_FOLDER=os.path.join(BASE, "static", "uploads"),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar."

serializador = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# ---------- ENVÍO DE CORREOS ----------
def enviar_correo(destino, asunto, cuerpo):
    servidor = os.environ.get("SMTP_SERVER")

    if not servidor:
        print(
            f"\n--- CORREO (modo desarrollo) ---\n"
            f"Para: {destino}\n"
            f"Asunto: {asunto}\n"
            f"{cuerpo}\n"
            f"--------------------------------\n"
        )
        return

    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(cuerpo)

    with smtplib.SMTP(
        servidor,
        int(os.environ.get("SMTP_PORT", 587)),
        timeout=10
    ) as s:
        s.starttls()
        s.login(
            os.environ["SMTP_USER"],
            os.environ["SMTP_PASSWORD"]
        )
        s.send_message(msg)


# ---------- CARGAR USUARIO ----------
@login_manager.user_loader
def cargar_usuario(user_id):
    return db.session.get(Usuario, int(user_id))


# ---------- INICIO ----------
@app.route("/")
def inicio():
    if current_user.is_authenticated:
        return redirect(url_for("mapa"))

    return redirect(url_for("login"))


# ---------- REGISTRO ----------
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":

        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not nombre or "@" not in email or len(password) < 8:
            flash(
                "Completa todos los campos. "
                "La contraseña debe tener mínimo 8 caracteres.",
                "error"
            )

        elif Usuario.query.filter_by(email=email).first():
            flash("El correo ya se encuentra registrado.", "error")

        else:
            usuario = Usuario(
                nombre=nombre,
                email=email,
                password_hash=generate_password_hash(password)
            )

            db.session.add(usuario)
            db.session.commit()

            flash("Cuenta creada. Ya puedes iniciar sesión.", "ok")
            return redirect(url_for("login"))

    return render_template("auth.html", modo="registro")


# ---------- INICIAR SESIÓN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and check_password_hash(usuario.password_hash, password):
            login_user(usuario)
            return redirect(url_for("mapa"))

        flash("Usuario o contraseña incorrectos.", "error")

    return render_template("auth.html", modo="login")


# ---------- CERRAR SESIÓN ----------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- RECUPERAR CONTRASEÑA ----------
@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario:
            token = serializador.dumps(
                {
                    "id": usuario.id,
                    "h": usuario.password_hash[-12:]
                },
                salt="recuperar"
            )

            enlace = url_for(
                "restablecer",
                token=token,
                _external=True
            )

            try:
                enviar_correo(
                    usuario.email,
                    "Recupera tu contraseña · Public Alert",
                    f"Hola {usuario.nombre},\n\n"
                    f"Entra a este enlace para crear una contraseña nueva "
                    f"(vence en 1 hora):\n{enlace}\n\n"
                    f"Si no fuiste tú, ignora este mensaje."
                )

            except Exception:
                app.logger.exception(
                    "No se pudo enviar el correo de recuperación"
                )

        flash(
            "Si el correo está registrado, te enviamos un enlace "
            "para recuperar tu contraseña.",
            "ok"
        )

        return redirect(url_for("login"))

    return render_template("recuperar.html")


# ---------- RESTABLECER CONTRASEÑA ----------
@app.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer(token):

    try:
        datos = serializador.loads(
            token,
            salt="recuperar",
            max_age=3600
        )

    except (SignatureExpired, BadSignature):
        flash(
            "El enlace no es válido o ya venció. Solicita uno nuevo.",
            "error"
        )
        return redirect(url_for("recuperar"))

    usuario = db.session.get(Usuario, datos["id"])

    if not usuario or usuario.password_hash[-12:] != datos["h"]:
        flash("Este enlace ya fue usado. Solicita uno nuevo.", "error")
        return redirect(url_for("recuperar"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")

        if len(password) < 8:
            flash("La contraseña debe tener mínimo 8 caracteres.", "error")

        elif password != confirmar:
            flash("Las contraseñas no coinciden.", "error")

        else:
            usuario.password_hash = generate_password_hash(password)
            db.session.commit()

            flash(
                "Contraseña actualizada. Ya puedes iniciar sesión.",
                "ok"
            )
            return redirect(url_for("login"))

    return render_template("restablecer.html")


# ---------- MAPA DE REPORTES ----------
@app.route("/mapa")
@login_required
def mapa():

    categoria = request.args.get("categoria", "")
    estado = request.args.get("estado", "")

    consulta = Reporte.query

    if categoria in CATEGORIAS:
        consulta = consulta.filter_by(categoria=categoria)

    if estado in ESTADOS:
        consulta = consulta.filter_by(estado=estado)

    reportes = consulta.order_by(Reporte.fecha.desc()).all()

    # Identificar los reportes que ya afectan al usuario actual
    mis_afectaciones = {
        a.reporte_id
        for a in Afectacion.query.filter_by(
            usuario_id=current_user.id
        ).all()
    }

    # Crear mapa
    m = folium.Map(
        location=[4.7110, -74.0721],
        zoom_start=12
    )

    for r in reportes:

        nota = ""

        if r.calificaciones:
            nota = (
                f"★ {r.promedio:.1f} "
                f"({len(r.calificaciones)})<br>"
            )

        popup = (
            f"<b>{escape(r.categoria)}</b><br>"
            f"{escape(r.descripcion[:80])}<br>"
            f"{nota}"
            f"<a href='{url_for('detalle', id=r.id)}' "
            f"target='_top'>Ver detalle</a>"
        )

        folium.Marker(
            [r.latitud, r.longitud],
            popup=folium.Popup(popup, max_width=240),
            tooltip=r.categoria,
            icon=folium.Icon(
                color=COLORES.get(r.categoria, "gray")
            )
        ).add_to(m)

    if reportes:
        m.fit_bounds(
            [[r.latitud, r.longitud] for r in reportes],
            max_zoom=16
        )

    return render_template(
        "mapa.html",
        mapa=m._repr_html_(),
        reportes=reportes,
        categorias=CATEGORIAS,
        estados=ESTADOS,
        f_categoria=categoria,
        f_estado=estado,
        mis_afectaciones=mis_afectaciones
    )


# ---------- CREAR REPORTE ----------
@app.route("/reportar", methods=["GET", "POST"])
@login_required
def reportar():

    if request.method == "POST":

        categoria = request.form.get("categoria", "")
        descripcion = request.form.get("descripcion", "").strip()
        foto = request.files.get("foto")

        lat = None
        lon = None

        try:
            lat = float(request.form.get("latitud", ""))
            lon = float(request.form.get("longitud", ""))

        except (ValueError, TypeError):
            direccion = request.form.get("direccion", "").strip()

            if direccion:
                try:
                    from geopy.geocoders import Nominatim

                    lugar = Nominatim(
                        user_agent="publicalert"
                    ).geocode(
                        direccion + ", Colombia",
                        timeout=5
                    )

                    if lugar:
                        lat = lugar.latitude
                        lon = lugar.longitude

                except Exception:
                    app.logger.exception(
                        "No se pudo geocodificar la dirección"
                    )

        ext = (
            foto.filename.rsplit(".", 1)[-1].lower()
            if foto and "." in foto.filename
            else ""
        )

        if categoria not in CATEGORIAS or not descripcion:
            flash(
                "Selecciona una categoría y escribe la descripción.",
                "error"
            )

        elif lat is None or lon is None:
            flash(
                "No pudimos obtener la ubicación. "
                "Permite el GPS o escribe la dirección.",
                "error"
            )

        elif ext not in EXTENSIONES:
            flash(
                "Adjunta una fotografía válida "
                "(jpg, png o webp, máximo 5 MB).",
                "error"
            )

        else:
            contenido_foto = foto.read()
            foto_base64 = f"data:{foto.content_type};base64,{base64.b64encode(contenido_foto).decode('utf-8')}"

            nuevo_reporte = Reporte(
                categoria=categoria,
                descripcion=descripcion,
                foto=foto_base64,
                latitud=lat,
                longitud=lon,
                usuario_id=current_user.id
            )

            db.session.add(nuevo_reporte)
            db.session.commit()

            flash("Reporte enviado correctamente.", "ok")
            return redirect(url_for("mapa"))

    return render_template(
        "reportar.html",
        categorias=CATEGORIAS
    )


# ---------- VER DETALLES DEL REPORTE ----------
@app.route("/reporte/<int:id>")
@login_required
def detalle(id):

    reporte = db.session.get(Reporte, id) or abort(404)

    mia = Calificacion.query.filter_by(
        reporte_id=id,
        usuario_id=current_user.id
    ).first()

    mi_afectacion = Afectacion.query.filter_by(
        reporte_id=id,
        usuario_id=current_user.id
    ).first()

    return render_template(
        "detalle.html",
        r=reporte,
        mia=mia,
        mi_afectacion=mi_afectacion
    )


# ---------- CALIFICAR REPORTE ----------
@app.route("/reporte/<int:id>/calificar", methods=["POST"])
@login_required
def calificar(id):

    reporte = db.session.get(Reporte, id) or abort(404)

    ya_voto = Calificacion.query.filter_by(
        reporte_id=id,
        usuario_id=current_user.id
    ).first()

    try:
        estrellas = int(request.form.get("estrellas", ""))

    except (ValueError, TypeError):
        estrellas = 0

    if reporte.usuario_id == current_user.id:
        flash("No puedes calificar tu propio reporte.", "error")

    elif ya_voto:
        flash(
            "Ya calificaste este reporte. "
            "No puedes calificarlo de nuevo.",
            "error"
        )

    elif not 1 <= estrellas <= 5:
        flash("Selecciona entre 1 y 5 estrellas.", "error")

    else:
        db.session.add(
            Calificacion(
                reporte_id=id,
                usuario_id=current_user.id,
                estrellas=estrellas
            )
        )

        db.session.commit()
        flash("¡Gracias por tu calificación!", "ok")

    return redirect(url_for("detalle", id=id))

@app.route('/admin')
@login_required
def panel_admin():
    # Criterio 1: Acceso restringido
    if not current_user.es_admin:
        flash('Acceso denegado: Se requiere rol de administrador.', 'error')
        return redirect(url_for('mapa'))
    
    reportes = Reporte.query.order_by(Reporte.fecha.desc()).all()
    
    # Criterio 4: Resumen de seguimiento
    conteo_estados = {estado: 0 for estado in ESTADOS}
    for r in reportes:
        if r.estado in conteo_estados:
            conteo_estados[r.estado] += 1
            
    return render_template('admin.html', reportes=reportes, estados=ESTADOS, conteo=conteo_estados)

@app.route('/admin/cambiar_estado/<int:id>', methods=['POST'])
@login_required
def cambiar_estado(id):
    if not current_user.es_admin:
        return redirect(url_for('mapa'))
        
    reporte = Reporte.query.get_or_404(id)
    nuevo_estado = request.form.get('estado')
    
    if nuevo_estado in ESTADOS:
        reporte.estado = nuevo_estado
        db.session.commit()
        flash('Estado actualizado correctamente.', 'ok')
        
    # ESTE RETURN DEBE ESTAR ALINEADO CON EL IF
    return redirect(url_for('panel_admin'))

@app.route('/admin/eliminar_reporte/<int:id>', methods=['POST'])
@login_required
def eliminar_reporte(id):
    if not current_user.es_admin:
        return redirect(url_for('mapa'))
        
    reporte = Reporte.query.get_or_404(id)
    
    # 1. NUEVO: Borrar las afectaciones asociadas al reporte
    # (Asegúrate de que el nombre del modelo sea exactamente Afectacion, si es distinto, cámbialo aquí)
    Afectacion.query.filter_by(reporte_id=id).delete()
    
    # 2. Borrar las calificaciones asociadas
    Calificacion.query.filter_by(reporte_id=id).delete()
    
    # 3. Borrar la foto del servidor
    if reporte.foto:
        ruta_foto = os.path.join('static', 'uploads', reporte.foto)
        if os.path.exists(ruta_foto):
            os.remove(ruta_foto)
            
    # 4. Finalmente, borrar el reporte
    db.session.delete(reporte)
    db.session.commit()
    
    flash('Reporte eliminado exitosamente.', 'ok')
    return redirect(url_for('panel_admin'))

# ---------- INDICAR QUE UN REPORTE ME AFECTA ----------
@app.route("/reporte/<int:id>/afecta", methods=["POST"])
@login_required
def afectar_reporte(id):

    reporte = db.session.get(Reporte, id) or abort(404)

    ya_afectado = Afectacion.query.filter_by(
        reporte_id=id,
        usuario_id=current_user.id
    ).first()

    if ya_afectado:
        flash(
            "Ya indicaste que este reporte te afecta.",
            "error"
        )

    else:
        nueva_afectacion = Afectacion(
            reporte_id=reporte.id,
            usuario_id=current_user.id
        )

        db.session.add(nueva_afectacion)

        try:
            db.session.commit()
            flash(
                "Tu participación fue registrada correctamente.",
                "ok"
            )

        except Exception:
            db.session.rollback()
            flash(
                "No se pudo registrar tu participación.",
                "error"
            )

    return redirect(url_for("mapa"))


# ---------- CONTROL DE ARCHIVOS GRANDES ----------
@app.errorhandler(413)
def archivo_grande(_):
    flash(
        "La imagen supera los 5 MB. Elige una más liviana.",
        "error"
    )
    return redirect(url_for("reportar"))

with app.app_context():
    db.create_all()
    try:
        # Modifica la columna foto en PostgreSQL para aceptar texto largo (Base64)
        db.session.execute(db.text("ALTER TABLE reporte ALTER COLUMN foto TYPE TEXT;"))
        db.session.commit()
    except Exception:
        db.session.rollback()

# ---------- EJECUTAR APLICACIÓN ----------
if __name__ == "__main__":
    app.run(debug=True)
