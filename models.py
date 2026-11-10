from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

CATEGORIAS = ["Baches", "Alumbrado", "Basura", "Seguridad", "Obras"]
ESTADOS = ["Pendiente", "En revisión", "Atendido"]
COLORES = {
    "Baches": "orange",
    "Alumbrado": "beige",
    "Basura": "green",
    "Seguridad": "red",
    "Obras": "blue"
}


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    reportes = db.relationship("Reporte", backref="autor", lazy=True)
    es_admin = db.Column(db.Boolean, default=False)


class Reporte(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(30), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    foto = db.Column(db.Text, nullable=False)
    latitud = db.Column(db.Float, nullable=False)
    longitud = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default="Pendiente", nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)

    @property
    def promedio(self):
        """Promedio de estrellas del reporte."""
        if not self.calificaciones:
            return None
        return sum(c.estrellas for c in self.calificaciones) / len(self.calificaciones)

    @property
    def total_afectados(self):
        """Cantidad de usuarios afectados por este reporte."""
        return len(self.afectaciones)


class Calificacion(db.Model):
    __tablename__ = "calificaciones"
    __table_args__ = (
        db.UniqueConstraint("reporte_id", "usuario_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey("reporte.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    estrellas = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)

    reporte = db.relationship("Reporte", backref="calificaciones")


class Afectacion(db.Model):
    __tablename__ = "afectaciones"

    __table_args__ = (
        db.UniqueConstraint("reporte_id", "usuario_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey("reporte.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now, nullable=False)

    reporte = db.relationship("Reporte", backref="afectaciones")
