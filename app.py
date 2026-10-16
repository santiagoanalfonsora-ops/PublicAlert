import os
import uuid
import folium
<<<<<<< HEAD
from sqlalchemy import func
=======
>>>>>>> cae67cc65f509089c2ece7b5478e9b7ab2da5d73
from markupsafe import escape
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
<<<<<<< HEAD
from models import db, Usuario, Reporte, Calificacion, CATEGORIAS, ESTADOS, COLORES
=======
from models import db, Usuario, Reporte, CATEGORIAS, ESTADOS, COLORES
>>>>>>> cae67cc65f509089c2ece7b5478e9b7ab2da5d73

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
        popup = (f"<b>{escape(r.categoria)}</b><br>{escape(r.descripcion[:80])}<br>"
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
<<<<<<< HEAD
    mia = Calificacion.query.filter_by(reporte_id=id, usuario_id=current_user.id).first()
    return render_template("detalle.html", r=reporte, mia=mia)


# ---------- Calificación de 1 a 5 estrellas (cualquier usuario, 1 voto por reporte) ----------
@app.route("/reporte/<int:id>/calificar", methods=["POST"])
@login_required
def calificar(id):
    reporte = db.session.get(Reporte, id) or abort(404)
    try:
        estrellas = int(request.form.get("estrellas", ""))
    except ValueError:
        estrellas = 0
    if reporte.estado != "Atendido":
        flash("Solo puedes calificar cuando el reporte esté atendido.", "error")
    elif not 1 <= estrellas <= 5:
        flash("Selecciona entre 1 y 5 estrellas.", "error")
    else:
        voto = Calificacion.query.filter_by(reporte_id=id, usuario_id=current_user.id).first()
        if voto:  # si ya había calificado, se actualiza su voto
            voto.estrellas = estrellas
            flash("Actualizamos tu calificación.", "ok")
        else:
            db.session.add(Calificacion(reporte_id=id, usuario_id=current_user.id, estrellas=estrellas))
            flash("¡Gracias por tu calificación!", "ok")
        db.session.commit()
    return redirect(url_for("detalle", id=id))


# ---------- Tablero kanban de reportes (solo administrador = primer usuario registrado) ----------
def es_admin():
    return current_user.is_authenticated and current_user.id == 1


@app.context_processor
def inyectar_admin():
    return {"es_admin": es_admin()}


@app.route("/kanban")
@login_required
def kanban():
    if not es_admin():
        abort(403)
    columnas = {e: Reporte.query.filter_by(estado=e).order_by(Reporte.fecha.desc()).all()
                for e in ESTADOS}
    promedio = db.session.query(func.avg(Calificacion.estrellas)).scalar()
    total = Calificacion.query.count()
    return render_template("kanban.html", columnas=columnas, estados=ESTADOS,
                           promedio=promedio, total=total)


@app.route("/reporte/<int:id>/estado", methods=["POST"])
@login_required
def cambiar_estado(id):
    if not es_admin():
        abort(403)
    reporte = db.session.get(Reporte, id) or abort(404)
    nuevo = request.form.get("estado")
    if nuevo in ESTADOS:
        reporte.estado = nuevo
        db.session.commit()
    return redirect(url_for("kanban"))
=======
    return render_template("detalle.html", r=reporte)
>>>>>>> cae67cc65f509089c2ece7b5478e9b7ab2da5d73


@app.errorhandler(413)
def archivo_grande(_):
    flash("La imagen supera los 5 MB. Elige una más liviana.", "error")
    return redirect(url_for("reportar"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
<<<<<<< HEAD
    app.run(debug=True)
=======
    app.run(debug=True)
>>>>>>> cae67cc65f509089c2ece7b5478e9b7ab2da5d73
