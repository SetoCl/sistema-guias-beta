from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import sqlite3
from datetime import date, datetime
import os
import io
import uuid
from urllib.parse import quote

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
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
            property TEXT,
            email_property TEXT
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

            tipo_trabajo TEXT,
            descripcion TEXT,

            estado TEXT,

            observaciones TEXT,

            token_revision TEXT
        )
    """)

    conn.execute("""

    CREATE TABLE IF NOT EXISTS mantenciones (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    cliente_id INTEGER,
    fecha_entrega TEXT,
    numero_guia INTEGER,

    mes INTEGER,
    anio INTEGER

    )

    """)

    conn.commit()
    conn.close()


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
        tipo_trabajo = request.form.get("tipo_trabajo")
        observaciones = request.form.get("observaciones")

        if guia_id:

            guia = conn.execute(
                "SELECT estado FROM guias WHERE id=?",
                (guia_id,)
            ).fetchone()

            if guia["estado"] == "CERRADA":
                conn.close()
                return "La guía está cerrada y no puede editarse"

            conn.execute("""
                UPDATE guias SET
                    fecha=?,
                    cliente_id=?,
                    tecnicos=?,
                    tipo_trabajo=?,
                    descripcion=?,
                    observaciones=?
                WHERE id=?
            """, (
                fecha, cliente_id, tecnicos,
                tipo_trabajo, descripcion,
                observaciones, guia_id
            ))

            conn.commit()

            guia = conn.execute("""
                SELECT numero_guia, token_revision
                FROM guias
                WHERE id=?
            """,(guia_id,)).fetchone()

            conn.close()

            link = request.host_url + "revision/" + guia["token_revision"]

            destinatarios = "psalinas@igpaseguridad.cl;ptapia@igpaseguridad.cl"

            asunto = quote(f"Revisión de trabajo - Guía {guia['numero_guia']}")

            cuerpo = quote(f"""
Estimados,

La guía N° {guia['numero_guia']} ha sido actualizada.

Para revisar y aprobar el trabajo utilicen el siguiente enlace:

{link}

Saludos
Fibratel
""")

            mailto = f"mailto:{destinatarios}?subject={asunto}&body={cuerpo}"

            return redirect(mailto)

        else:

            ultimo = conn.execute(
                "SELECT MAX(numero_guia) FROM guias"
            ).fetchone()[0]

            nuevo_numero = (ultimo + 1) if ultimo else 1

            token = str(uuid.uuid4())

            cursor = conn.execute("""
                INSERT INTO guias
                (numero_guia, fecha, cliente_id, tecnicos,
                 tipo_trabajo, descripcion,
                 estado, observaciones, token_revision)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nuevo_numero,
                fecha,
                cliente_id,
                tecnicos,
                tipo_trabajo,
                descripcion,
                "ABIERTA",
                observaciones,
                token
            ))

            guia_id = cursor.lastrowid

            conn.commit()
            conn.close()

            return redirect(url_for("confirmacion_guia", guia_id=guia_id))

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

    clientes = conn.execute(
        "SELECT * FROM clientes ORDER BY nombre"
    ).fetchall()

    tecnicos = conn.execute(
        "SELECT * FROM tecnicos ORDER BY nombre"
    ).fetchall()

    ultimo = conn.execute(
        "SELECT MAX(numero_guia) FROM guias"
    ).fetchone()[0]

    proximo_numero = (ultimo + 1) if ultimo else 1

    # ---------------- DASHBOARD ----------------

    abiertas = conn.execute(
        "SELECT COUNT(*) FROM guias WHERE estado='ABIERTA'"
    ).fetchone()[0]

    cerradas = conn.execute(
        "SELECT COUNT(*) FROM guias WHERE estado='CERRADA'"
    ).fetchone()[0]

    hoy = conn.execute(
        "SELECT COUNT(*) FROM guias WHERE fecha=?",
        (date.today(),)
    ).fetchone()[0]

    tecnicos_data = conn.execute(
        "SELECT tecnicos FROM guias"
    ).fetchall()

    conteo = {}

    for r in tecnicos_data:

        if not r["tecnicos"]:
            continue

        lista = r["tecnicos"].split(", ")

        for t in lista:
            conteo[t] = conteo.get(t,0)+1

    lider = "-"

    if conteo:
        lider = max(conteo, key=conteo.get)

    conn.close()

    return render_template(
    "index.html",
    fecha=date.today(),
    clientes=clientes,
    tecnicos=tecnicos,
    guia=guia,
    proximo_numero=proximo_numero,
    abiertas=abiertas,
    cerradas=cerradas,
    hoy=hoy,
    lider=lider
)

# =========================================================
# CONFIRMACION GUIA
# =========================================================
@app.route("/confirmacion/<int:guia_id>")
def confirmacion_guia(guia_id):

    conn = get_db()

    guia = conn.execute("""
        SELECT id, numero_guia, token_revision
        FROM guias
        WHERE id = ?
    """,(guia_id,)).fetchone()

    conn.close()

    link_revision = request.host_url + "revision/" + guia["token_revision"]

    return render_template(
        "confirmacion.html",
        guia=guia,
        link_revision=link_revision
    )

# =========================================================
# PROPERTY REVISION
# =========================================================
@app.route("/revision/<token>")
def revision(token):

    conn = get_db()

    guia = conn.execute("""
        SELECT g.*, c.nombre as cliente,
               c.direccion, c.property
        FROM guias g
        LEFT JOIN clientes c ON g.cliente_id = c.id
        WHERE g.token_revision=?
    """, (token,)).fetchone()

    conn.close()

    if guia is None:
        return "Guía no encontrada"

    return render_template("revision.html", guia=guia)


@app.route("/aceptar/<token>")
def aceptar_trabajo(token):

    conn = get_db()

    conn.execute("""
        UPDATE guias
        SET estado='CERRADA'
        WHERE token_revision=?
    """, (token,))

    conn.commit()
    conn.close()

    return "Trabajo aceptado. La guía ha sido cerrada."


# =========================================================
# PDF
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

    styles = getSampleStyleSheet()
    elements = []

    azul = colors.HexColor("#0072CE")

    # LOGO + ENCABEZADO
    logo_path = os.path.join("static", "logo.png")

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=4*cm, height=2*cm)
    else:
        logo = ""

    header = Table([
        [logo, "FIBRATEL SPA"],
        ["", "Servicios de Fibra Óptica"]
    ], colWidths=[4*cm,12*cm])

    header.setStyle([
        ('FONTNAME',(1,0),(1,0),'Helvetica-Bold'),
        ('FONTSIZE',(1,0),(1,0),16),
        ('FONTSIZE',(1,1),(1,1),10),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE')
    ])

    elements.append(header)
    elements.append(Spacer(1,20))

    # LINEA AZUL
    linea = Table([[""]], colWidths=[16*cm])
    linea.setStyle([
        ('BACKGROUND',(0,0),(-1,-1),azul)
    ])

    elements.append(linea)
    elements.append(Spacer(1,15))

    # TITULO
    titulo = Paragraph(
        f"<b>GUÍA DE SERVICIO N° {guia['numero_guia']}</b>",
        styles["Heading2"]
    )

    elements.append(titulo)
    elements.append(Spacer(1,15))

    # DATOS
    data = [
        ["Fecha", guia["fecha"]],
        ["Cliente", guia["cliente"] or ""],
        ["Dirección", guia["direccion"] or ""],
        ["Property", guia["property"] or ""],
        ["Técnicos", guia["tecnicos"] or ""],
        ["Tipo de trabajo", guia["tipo_trabajo"] or ""],
        ["Estado", guia["estado"]]
    ]

    table = Table(data, colWidths=[4*cm,12*cm])

    table.setStyle([
        ('BACKGROUND',(0,0),(0,-1),colors.whitesmoke),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE')
    ])

    elements.append(table)
    elements.append(Spacer(1,25))

    # DESCRIPCION
    elements.append(
        Paragraph("<b>DESCRIPCIÓN DEL SERVICIO</b>", styles["Heading3"])
    )

    elements.append(Spacer(1,10))

    elements.append(
        Paragraph(guia["descripcion"] or "", styles["Normal"])
    )

    elements.append(Spacer(1,25))

    # OBSERVACIONES
    if guia["observaciones"]:

        elements.append(
            Paragraph("<b>OBSERVACIONES</b>", styles["Heading3"])
        )

        elements.append(Spacer(1,10))

        elements.append(
            Paragraph(guia["observaciones"], styles["Normal"])
        )

        elements.append(Spacer(1,25))

    # FIRMAS
    firma = Table([
        ["__________________________", "__________________________"],
        ["Firma Técnico", "Firma Cliente / Property"]
    ], colWidths=[8*cm,8*cm])

    firma.setStyle([
    ('ALIGN', (0,0), (-1,-1), 'CENTER')
])
    elements.append(firma)
    elements.append(Spacer(1,30))

    # PIE
    texto = f"""
    Emitido el {datetime.now().strftime('%d-%m-%Y %H:%M')}<br/>
    <b>FIBRATEL SPA</b><br/>
    Servicios de Fibra Óptica<br/>
    Soporte técnico especializado
    """

    elements.append(
        Paragraph(texto, styles["Normal"])
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
        return jsonify({
            "direccion": "",
            "property": ""
        })

# =========================================================
# REPORTES
# =========================================================
@app.route("/reportes")
def reportes():

    estado = request.args.get("estado")

    conn = get_db()

    query = """
        SELECT g.*, c.nombre as cliente
        FROM guias g
        LEFT JOIN clientes c ON g.cliente_id = c.id
        WHERE 1=1
    """

    params = []

    if estado:
        query += " AND g.estado = ?"
        params.append(estado)

    query += " ORDER BY g.numero_guia DESC"

    guias = conn.execute(query, params).fetchall()

    conn.close()

    return render_template("reportes.html", guias=guias)

# =========================================================
# MANTENCIONES
# =========================================================
@app.route("/mantenciones")
def mantenciones():

    mes = int(request.args.get("mes", date.today().month))
    anio = int(request.args.get("anio", date.today().year))

    conn = get_db()

    # ==========================
    # EDIFICIOS
    # ==========================

    edificios = conn.execute("""
        SELECT id, nombre
        FROM clientes
        ORDER BY nombre
    """).fetchall()

    total_edificios = len(edificios)

    # ==========================
    # RANGO MES ACTUAL
    # ==========================

    inicio = f"{anio}-{mes:02d}-01"

    if mes == 12:
        fin = f"{anio+1}-01-01"
    else:
        fin = f"{anio}-{mes+1:02d}-01"


    # ==========================
    # MES ANTERIOR
    # ==========================

    if mes == 1:
        mes_ant = 12
        anio_ant = anio - 1
    else:
        mes_ant = mes - 1
        anio_ant = anio

    inicio_ant = f"{anio_ant}-{mes_ant:02d}-01"

    if mes_ant == 12:
        fin_ant = f"{anio_ant+1}-01-01"
    else:
        fin_ant = f"{anio_ant}-{mes_ant+1:02d}-01"


    # ==========================
    # MANTENCIONES MES ACTUAL
    # ==========================

    mantenciones_mes = conn.execute("""

        SELECT cliente_id, fecha, numero_guia
        FROM guias

        WHERE tipo_trabajo LIKE '%MANTENC%'
        AND fecha >= ?
        AND fecha < ?

    """,(inicio,fin)).fetchall()


    # ==========================
    # MANTENCIONES MES ANTERIOR
    # ==========================

    historial = conn.execute("""

        SELECT cliente_id, fecha
        FROM guias

        WHERE tipo_trabajo LIKE '%MANTENC%'
        AND fecha >= ?
        AND fecha < ?

    """,(inicio_ant,fin_ant)).fetchall()

    conn.close()


    # ==========================
    # DICCIONARIOS
    # ==========================

    mant_dic = {
        m["cliente_id"]: m
        for m in mantenciones_mes
    }

    hist_dic = {
        h["cliente_id"]: h["fecha"]
        for h in historial
    }


    # ==========================
    # LISTA FINAL
    # ==========================

    lista = []

    edificios_listos = 0

    for e in edificios:

        mant_mes = mant_dic.get(e["id"])
        anterior = hist_dic.get(e["id"])

        if mant_mes:
            fecha_mes = mant_mes["fecha"]
            guia = mant_mes["numero_guia"]
            edificios_listos += 1
        else:
            fecha_mes = None
            guia = None

        lista.append({

            "edificio": e["nombre"],
            "anterior": anterior,
            "mes": fecha_mes,
            "guia": guia

        })


    # ==========================
    # DASHBOARD
    # ==========================

    mantenciones_mes_total = edificios_listos

    pendientes = total_edificios - mantenciones_mes_total


    return render_template(

    "mantenciones.html",

    mantenciones=lista,
    mes=mes,
    anio=anio,

    total_edificios=total_edificios,
    mantenciones_mes_total=mantenciones_mes_total,
    pendientes=pendientes
)

# =========================================================
# ESTADISTICAS EDIFICIOS
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

if __name__ == "__main__":
    app.run(debug=True)