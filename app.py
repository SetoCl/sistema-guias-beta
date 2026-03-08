from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import sqlite3
from datetime import date, datetime
import os
import io

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import cm
from reportlab.lib import colors

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            direccion TEXT,
            property TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tecnicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS guias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_guia INTEGER UNIQUE,
            fecha TEXT,
            cliente_id INTEGER,
            tecnicos TEXT,
            tecnico_firma TEXT,
            descripcion TEXT,
            estado TEXT,
            observaciones TEXT
        )
    """)

    conn.commit()
    conn.close()


# 🔥 IMPORTANTE: Se ejecuta siempre (local y Render)
init_db()


# =========================================================
# INDEX
# =========================================================
@app.route("/", methods=["GET", "POST"])
def index():

    conn = get_db()

    if request.method == "POST":

        guia_id = request.form.get("guia_id")
        fecha = request.form.get("fecha")
        cliente_id = request.form.get("cliente_id")
        tecnicos = request.form.get("tecnicos")
        descripcion = request.form.get("descripcion")
        estado = request.form.get("estado")
        observaciones = request.form.get("observaciones")

        if guia_id:
            conn.execute("""
                UPDATE guias SET
                    fecha=?,
                    cliente_id=?,
                    tecnicos=?,
                    descripcion=?,
                    estado=?,
                    observaciones=?
                WHERE id=?
            """, (
                fecha, cliente_id, tecnicos,
                descripcion, estado, observaciones, guia_id
            ))

            conn.commit()
            conn.close()
            return redirect(url_for("generar_pdf", guia_id=guia_id))

        else:
            ultimo = conn.execute(
                "SELECT MAX(numero_guia) FROM guias"
            ).fetchone()[0]

            nuevo_numero = (ultimo + 1) if ultimo else 1

            cursor = conn.execute("""
                INSERT INTO guias
                (numero_guia, fecha, cliente_id, tecnicos,
                 descripcion, estado, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nuevo_numero, fecha, cliente_id,
                tecnicos, descripcion, estado, observaciones
            ))

            guia_id = cursor.lastrowid
            conn.commit()
            conn.close()

            return redirect(url_for("generar_pdf", guia_id=guia_id))

    guia_id = request.args.get("editar")
    guia = None

    if guia_id:
        guia = conn.execute("""
            SELECT g.*,
                   c.nombre as cliente_nombre,
                   c.direccion,
                   c.property
            FROM guias g
            LEFT JOIN clientes c ON g.cliente_id = c.id
            WHERE g.id=?
        """, (guia_id,)).fetchone()

    clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    tecnicos = conn.execute("SELECT * FROM tecnicos ORDER BY nombre").fetchall()

    ultimo = conn.execute("SELECT MAX(numero_guia) FROM guias").fetchone()[0]
    proximo_numero = (ultimo + 1) if ultimo else 1

    conn.close()

    return render_template("index.html",
                           fecha=date.today(),
                           clientes=clientes,
                           tecnicos=tecnicos,
                           guia=guia,
                           proximo_numero=proximo_numero)

# =========================================================
# REPORTES
# =========================================================
@app.route("/reportes")
def reportes():

    cliente_id = request.args.get("cliente_id")
    inicio = request.args.get("inicio")
    fin = request.args.get("fin")

    conn = get_db()

    query = """
        SELECT g.*, c.nombre as cliente
        FROM guias g
        LEFT JOIN clientes c ON g.cliente_id = c.id
        WHERE 1=1
    """

    params = []

    if cliente_id:
        query += " AND g.cliente_id = ?"
        params.append(cliente_id)

    if inicio:
        query += " AND g.fecha >= ?"
        params.append(inicio)

    if fin:
        query += " AND g.fecha <= ?"
        params.append(fin)

    query += " ORDER BY g.numero_guia DESC"

    guias = conn.execute(query, params).fetchall()
    clientes = conn.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()

    conn.close()

    return render_template("reportes.html",
                           guias=guias,
                           clientes=clientes,
                           cliente_id=cliente_id,
                           inicio=inicio,
                           fin=fin)


# =========================================================
# PDF COMPLETO
# =========================================================
@app.route("/pdf/<int:guia_id>")
def generar_pdf(guia_id):

    conn = get_db()

    guia = conn.execute("""
        SELECT g.*, c.nombre as cliente,
               c.direccion, c.property
        FROM guias g
        LEFT JOIN clientes c ON g.cliente_id = c.id
        WHERE g.id = ?
    """, (guia_id,)).fetchone()

    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    elements = []
    styles = getSampleStyleSheet()
    azul = colors.HexColor("#0072CE")

    elements.append(Paragraph("<b>FIBRATEL SPA</b>", styles["Heading2"]))
    elements.append(Paragraph("RUT: 76.xxx.xxx-x", styles["Normal"]))
    elements.append(Paragraph("Santiago, Chile", styles["Normal"]))
    elements.append(Paragraph("contacto@fibratel.cl | +56 9 xxxx xxxx", styles["Normal"]))
    elements.append(Spacer(1, 15))

    linea = Table([[""]], colWidths=[16*cm])
    linea.setStyle([
        ('BACKGROUND', (0, 0), (-1, -1), azul)
    ])
    elements.append(linea)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>GUÍA DE SERVICIO</b>", styles["Heading1"]))
    elements.append(Spacer(1, 20))

    data = [
        ["N° Guía", str(guia["numero_guia"])],
        ["Fecha", guia["fecha"]],
        ["Cliente", guia["cliente"] or ""],
        ["Dirección", guia["direccion"] or ""],
        ["Property", guia["property"] or ""],
        ["Técnicos", guia["tecnicos"] or ""],
        ["Estado", guia["estado"]]
    ]

    table = Table(data, colWidths=[4*cm, 11*cm])
    table.setStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ])

    elements.append(table)
    elements.append(Spacer(1, 25))

    elements.append(Paragraph("<b>Descripción del Servicio</b>", styles["Heading3"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(guia["descripcion"] or "", styles["Normal"]))
    elements.append(Spacer(1, 25))

    if guia["observaciones"]:
        elements.append(Paragraph("<b>Observaciones</b>", styles["Heading3"]))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(guia["observaciones"], styles["Normal"]))
        elements.append(Spacer(1, 25))

    firma = Table([
        ["__________________________", "__________________________"],
        ["Firma Técnico", "Firma Cliente / Property"]
    ], colWidths=[8*cm, 8*cm])

    firma.setStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ])

    elements.append(firma)
    elements.append(Spacer(1, 30))

    elements.append(
        Paragraph(
            f"Emitido el {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            styles["Normal"]
        )
    )

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=False,
        download_name=f"guia_{guia['numero_guia']}.pdf",
        mimetype="application/pdf"
    )


# =========================================================
# ESTADISTICAS TECNICOS
# =========================================================
@app.route("/estadisticas")
def estadisticas():

    inicio = request.args.get("inicio")
    fin = request.args.get("fin")

    conn = get_db()

    query = "SELECT tecnicos FROM guias WHERE 1=1"
    params = []

    if inicio:
        query += " AND fecha >= ?"
        params.append(inicio)

    if fin:
        query += " AND fecha <= ?"
        params.append(fin)

    registros = conn.execute(query, params).fetchall()
    conn.close()

    conteo = {}

    for r in registros:
        if not r["tecnicos"]:
            continue

        lista = r["tecnicos"].split(", ")

        for t in lista:
            conteo[t] = conteo.get(t, 0) + 1

    labels = list(conteo.keys())
    valores = list(conteo.values())

    total = sum(valores)
    tecnicos = len(labels)

    promedio = 0
    if tecnicos > 0:
        promedio = round(total / tecnicos)

    lider = "-"
    if valores:
        i = valores.index(max(valores))
        lider = labels[i]

    return render_template(
    "estadisticas.html",
    labels=labels,
    valores=valores,
    inicio=inicio,
    fin=fin,
    total=total,
    tecnicos=tecnicos,
    promedio=promedio,
    lider=lider
)



# =========================================================
# API CLIENTE
# =========================================================
@app.route("/api/cliente/<int:cliente_id>")
def api_cliente(cliente_id):

    conn = get_db()

    cliente = conn.execute(
        "SELECT direccion, property FROM clientes WHERE id=?",
        (cliente_id,)
    ).fetchone()

    conn.close()

    if cliente:
        return jsonify(dict(cliente))
    else:
        return jsonify({"direccion": "", "property": ""})


# =========================================================
# ESTADISTICAS POR EDIFICIO
# =========================================================
@app.route("/estadisticas_edificio")
def estadisticas_edificio():

    inicio = request.args.get("inicio")
    fin = request.args.get("fin")

    conn = get_db()

    query = """
        SELECT c.nombre as cliente, COUNT(g.id) as total
        FROM guias g
        LEFT JOIN clientes c ON g.cliente_id = c.id
        WHERE 1=1
    """
    params = []

    if inicio:
        query += " AND g.fecha >= ?"
        params.append(inicio)

    if fin:
        query += " AND g.fecha <= ?"
        params.append(fin)

    query += " GROUP BY c.nombre ORDER BY total DESC"

    datos = conn.execute(query, params).fetchall()
    conn.close()

    labels = [d["cliente"] for d in datos]
    valores = [d["total"] for d in datos]

    total = sum(valores)
    edificios = len(labels)

    promedio = 0
    if edificios > 0:
        promedio = round(total / edificios)

    lider = "-"
    if valores:
        i = valores.index(max(valores))
        lider = labels[i]

    return render_template(
        "estadisticas_edificio.html",
        labels=labels,
        valores=valores,
        inicio=inicio,
        fin=fin,
        total=total,
        edificios=edificios,
        promedio=promedio,
        lider=lider
    )


if __name__ == "__main__":
    app.run(debug=True)