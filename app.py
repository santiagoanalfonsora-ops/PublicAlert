import os
import smtplib
import uuid
import folium
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from markupsafe import escape
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Usuario, Reporte, Calificacion, CATEGORIAS, ESTADOS, COLORES

BASE = os.path.abspath(os.path.dirname(__file__))
EXTENSIONES = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "cambiar-en-produccion"),
    SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(BASE, "publicalert.db"),
    UPLOAD_FOLDER=os.path.join(BASE, "static", "uploads"),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB por foto
)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar."
serializador = URLSafeTimedSerializer(app.config["SECRET_KEY"])


def enviar_correo(destino, asunto, cuerpo):
    """Envía el correo por SMTP si hay configuración; si no, lo imprime en la terminal (modo desarrollo)."""
    servidor = os.environ.get("SMTP_SERVER")
    if not servidor:
        print(f"\n--- CORREO (modo desarrollo) ---\nPara: {destino}\nAsunto: {asunto}\n{cuerpo}\n--------------------------------\n")
        return
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    with smtplib.SMTP(servidor, int(os.environ.get("SMTP_PORT", 587)), timeout=10) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)


@login_manager.user_loader
def cargar_usuario(user_id):
    return db.session.get(Usuario, int(user_id))


@app.route("/")
def inicio():
    return redirect(url_for("mapa" if current_user.is_authenticated else "login"))


# ---------- CU01: Registrar usuario ----------
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not nombre or "@" not in email or len(password) < 8:
            flash("Completa todos los campos. La contraseña debe tener mínimo 8 caracteres.", "error")
        elif Usuario.query.filter_by(email=email).first():
            flash("El correo ya se encuentra registrado.", "error")
        else:
            db.session.add(Usuario(nombre=nombre, email=email,
                                   password_hash=generate_password_hash(password)))
            db.session.commit()
            flash("Cuenta creada. Ya puedes iniciar sesión.", "ok")
            return redirect(url_for("login"))
    return render_template("auth.html", modo="registro")


# ---------- CU02: Iniciar sesión ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.password_hash, request.form.get("password", "")):
            login_user(usuario)
            return redirect(url_for("mapa"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("auth.html", modo="login")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- HU-004: Recuperar contraseña ----------
@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario:
            token = serializador.dumps({"id": usuario.id, "h": usuario.password_hash[-12:]}, salt="recuperar")
            enlace = url_for("restablecer", token=token, _external=True)
            try:
                enviar_correo(usuario.email, "Recupera tu contraseña · Public Alert",
                              f"Hola {usuario.nombre},\n\nEntra a este enlace para crear una contraseña nueva "
                              f"(vence en 1 hora):\n{enlace}\n\nSi no fuiste tú, ignora este mensaje.")
            except Exception:
                app.logger.exception("No se pudo enviar el correo de recuperación")
        # Mismo mensaje exista o no el correo, para no revelar qué correos están registrados
        flash("Si el correo está registrado, te enviamos un enlace para recuperar tu contraseña.", "ok")
        return redirect(url_for("login"))
    return render_template("recuperar.html")


@app.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer(token):
    try:
        datos = serializador.loads(token, salt="recuperar", max_age=3600)  # vence en 1 hora
    except (SignatureExpired, BadSignature):
        flash("El enlace no es válido o ya venció. Solicita uno nuevo.", "error")
        return redirect(url_for("recuperar"))
    usuario = db.session.get(Usuario, datos["id"])
    if not usuario or usuario.password_hash[-12:] != datos["h"]:  # el enlace se invalida al cambiar la clave
        flash("Este enlace ya fue usado. Solicita uno nuevo.", "error")
        return redirect(url_for("recuperar"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("La contraseña debe tener mínimo 8 caracteres.", "error")
        elif password != request.form.get("confirmar", ""):
            flash("Las contraseñas no coinciden.", "error")
        else:
            usuario.password_hash = generate_password_hash(password)
            db.session.commit()
            flash("Contraseña actualizada. Ya puedes iniciar sesión.", "ok")
            return redirect(url_for("login"))
    return render_template("restablecer.html")


# ---------- CU06: Consultar mapa de reportes (HU-003 filtros) ----------
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

    m = folium.Map(location=[4.7110, -74.0721], zoom_start=12)  # Bogotá
    for r in reportes:
        nota = f"★ {r.promedio:.1f} ({len(r.calificaciones)})<br>" if r.calificaciones else ""
        popup = (f"<b>{escape(r.categoria)}</b><br>{escape(r.descripcion[:80])}<br>{nota}"
                 f"<a href='{url_for('detalle', id=r.id)}' target='_top'>Ver detalle</a>")
        folium.Marker([r.latitud, r.longitud], popup=folium.Popup(popup, max_width=240),
                      tooltip=r.categoria,
                      icon=folium.Icon(color=COLORES.get(r.categoria, "gray"))).add_to(m)
    if reportes:
        m.fit_bounds([[r.latitud, r.longitud] for r in reportes], max_zoom=16)
    return render_template("mapa.html", mapa=m._repr_html_(), reportes=reportes,
                           categorias=CATEGORIAS, estados=ESTADOS,
                           f_categoria=categoria, f_estado=estado)


# ---------- CU03 + CU04 + CU05: Crear reporte ----------
@app.route("/reportar", methods=["GET", "POST"])
@login_required
def reportar():
    if request.method == "POST":
        categoria = request.form.get("categoria", "")
        descripcion = request.form.get("descripcion", "").strip()
        foto = request.files.get("foto")
        try:
            lat = float(request.form.get("latitud", ""))
            lon = float(request.form.get("longitud", ""))
        except ValueError:
            lat = lon = None
            direccion = request.form.get("direccion", "").strip()
            if direccion:  # alternativa si no hay GPS: geocodificar la dirección
                try:
                    from geopy.geocoders import Nominatim
                    lugar = Nominatim(user_agent="publicalert").geocode(direccion + ", Colombia", timeout=5)
                    if lugar:
                        lat, lon = lugar.latitude, lugar.longitude
                except Exception:
                    pass

        ext = foto.filename.rsplit(".", 1)[-1].lower() if foto and "." in foto.filename else ""
        if categoria not in CATEGORIAS or not descripcion:
            flash("Selecciona una categoría y escribe la descripción.", "error")
        elif lat is None:
            flash("No pudimos obtener la ubicación. Permite el GPS o escribe la dirección.", "error")
        elif ext not in EXTENSIONES:
            flash("Adjunta una fotografía válida (jpg, png o webp, máximo 5 MB).", "error")
        else:
            nombre = f"{uuid.uuid4().hex}.{ext}"
            foto.save(os.path.join(app.config["UPLOAD_FOLDER"], nombre))
            db.session.add(Reporte(categoria=categoria, descripcion=descripcion, foto=nombre,
                                   latitud=lat, longitud=lon, usuario_id=current_user.id))
            db.session.commit()
            flash("Reporte enviado correctamente.", "ok")
            return redirect(url_for("mapa"))
    return render_template("reportar.html", categorias=CATEGORIAS)


# ---------- CU07: Ver detalles de incidente ----------
@app.route("/reporte/<int:id>")
@login_required
def detalle(id):
    reporte = db.session.get(Reporte, id) or abort(404)
    mia = Calificacion.query.filter_by(reporte_id=id, usuario_id=current_user.id).first()
    return render_template("detalle.html", r=reporte, mia=mia)


# ---------- Calificación de 1 a 5 estrellas (otros usuarios, un solo voto por reporte) ----------
@app.route("/reporte/<int:id>/calificar", methods=["POST"])
@login_required
def calificar(id):
    reporte = db.session.get(Reporte, id) or abort(404)
    ya_voto = Calificacion.query.filter_by(reporte_id=id, usuario_id=current_user.id).first()
    try:
        estrellas = int(request.form.get("estrellas", ""))
    except ValueError:
        estrellas = 0
    if reporte.usuario_id == current_user.id:
        flash("No puedes calificar tu propio reporte.", "error")
    elif ya_voto:
        flash("Ya calificaste este reporte. No puedes calificarlo de nuevo.", "error")
    elif not 1 <= estrellas <= 5:
        flash("Selecciona entre 1 y 5 estrellas.", "error")
    else:
        db.session.add(Calificacion(reporte_id=id, usuario_id=current_user.id, estrellas=estrellas))
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
    
    # Borrar las calificaciones asociadas
    Calificacion.query.filter_by(reporte_id=id).delete()
    
    # Borrar la foto del servidor
    if reporte.foto:
        ruta_foto = os.path.join('static', 'uploads', reporte.foto)
        if os.path.exists(ruta_foto):
            os.remove(ruta_foto)
            
    # Borrar el reporte
    db.session.delete(reporte)
    db.session.commit()
    
    flash('Reporte eliminado exitosamente.', 'ok')
    return redirect(url_for('panel_admin'))


@app.errorhandler(413)
def archivo_grande(_):
    flash("La imagen supera los 5 MB. Elige una más liviana.", "error")
    return redirect(url_for("reportar"))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)