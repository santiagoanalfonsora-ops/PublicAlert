from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

CATEGORIAS = ["Baches", "Alumbrado", "Basura", "Seguridad", "Obras"]
ESTADOS = ["Pendiente", "En revisión", "Atendido"]
COLORES = {"Baches": "orange", "Alumbrado": "beige", "Basura": "green",
           "Seguridad": "red", "Obras": "blue"}


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    reportes = db.relationship("Reporte", backref="autor", lazy=True)


class Reporte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    foto = db.Column(db.String(255), nullable=False)      # nombre del archivo en static/uploads
    latitud = db.Column(db.Float, nullable=False)          # UbicacionGPS
    longitud = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default="Pendiente", nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
