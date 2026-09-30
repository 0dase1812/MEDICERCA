"""Load a small, repeatable demo data set. Usage: ``python -m app.seed``."""
from datetime import date, timedelta

import app.models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.ips_db import crear_tablas_ips_registradas, ips_session
from app.models.ips import InstitucionPrestadora, TipoIntegracionIPS
from app.models.medicamento import CondicionVenta, Medicamento
from app.models.usuario import EPS
from app.models_ips import HistoriaClinica, Inventario, PrescripcionActiva, PuntoVenta


def obtener_o_crear(db, modelo, defaults=None, **filtros):
    instancia = db.query(modelo).filter_by(**filtros).first()
    if instancia is None:
        instancia = modelo(**filtros, **(defaults or {}))
        db.add(instancia)
        db.flush()
    return instancia


def cargar() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Central, dynamic IPS registry. URLs remain in environment via clave_conexion.
        ips_1 = obtener_o_crear(db, InstitucionPrestadora, codigo="IPS-VITALIS", defaults={"nombre_ficticio": "IPS Vitalis Central", "clave_conexion": "demo_ips_1", "tipo_integracion": TipoIntegracionIPS.BASE_DATOS_DIRECTA})
        ips_2 = obtener_o_crear(db, InstitucionPrestadora, codigo="IPS-SOMOS", defaults={"nombre_ficticio": "IPS Somos Salud", "clave_conexion": "demo_ips_2", "tipo_integracion": TipoIntegracionIPS.BASE_DATOS_DIRECTA})
        ips_3 = obtener_o_crear(db, InstitucionPrestadora, codigo="IPS-RED", defaults={"nombre_ficticio": "IPS Red Continuo", "clave_conexion": "demo_ips_3", "tipo_integracion": TipoIntegracionIPS.BASE_DATOS_DIRECTA})
        obtener_o_crear(db, EPS, nombre_ficticio="Salud Total Simulada")
        obtener_o_crear(db, EPS, nombre_ficticio="Nueva Vida EPS (ficticia)")

        # (clave, registro_sanitario, nombre_generico, nombre_comercial, dosis,
        #  presentacion, condicion_venta, control_especial, indicaciones_uso,
        #  cantidad_por_entrega, duracion_tratamiento_dias).
        # Las primeras tres claves (acetaminofen/losartan/tramadol) se
        # referencian mas abajo para el inventario y la historia clinica de
        # demo — no cambiar esas claves sin actualizar esas referencias. Las
        # demas solo pueblan el catalogo (no tienen inventario asociado).
        catalogo = [
            ("acetaminofen", "INVIMA-SIM-0001", "Acetaminofen", "Dolex", "500 mg", "Caja x 20 tabletas", CondicionVenta.OTC, False, "Tomar 1 tableta cada 8 horas si hay dolor o fiebre.", "1 caja", 10),
            ("losartan", "INVIMA-SIM-0002", "Losartan", "Cozaar", "50 mg", "Caja x 30 tabletas", CondicionVenta.RX, False, "Tomar 1 tableta cada 24 horas, con o sin alimentos.", "2 cajas", 60),
            ("tramadol", "INVIMA-SIM-0003", "Tramadol", "Tramal", "50 mg", "Caja x 10 capsulas", CondicionVenta.RX, True, "Tomar 1 capsula cada 8 horas, maximo 5 dias seguidos.", "1 caja", 5),
            ("ibuprofeno", "INVIMA-SIM-0004", "Ibuprofeno", "Advil", "400 mg", "Caja x 30 tabletas", CondicionVenta.OTC, False, "Tomar 1 tableta cada 8 horas con alimentos.", "1 caja", 10),
            ("amoxicilina", "INVIMA-SIM-0005", "Amoxicilina", "Amoxil", "500 mg", "Caja x 21 capsulas", CondicionVenta.RX, False, "Tomar 1 capsula cada 8 horas durante 7 dias completos.", "1 caja", 7),
            ("metformina", "INVIMA-SIM-0006", "Metformina", "Glucophage", "850 mg", "Caja x 30 tabletas", CondicionVenta.RX, False, "Tomar 1 tableta cada 12 horas con las comidas.", "2 cajas", 60),
            ("omeprazol", "INVIMA-SIM-0007", "Omeprazol", "Losec", "20 mg", "Caja x 14 capsulas", CondicionVenta.OTC, False, "Tomar 1 capsula en ayunas cada 24 horas.", "2 cajas", 30),
            ("loratadina", "INVIMA-SIM-0008", "Loratadina", "Clarityne", "10 mg", "Caja x 10 tabletas", CondicionVenta.OTC, False, "Tomar 1 tableta cada 24 horas.", "1 caja", 10),
            ("cetirizina", "INVIMA-SIM-0009", "Cetirizina", "Zyrtec", "10 mg", "Caja x 20 tabletas", CondicionVenta.OTC, False, "Tomar 1 tableta cada 24 horas.", "1 caja", 20),
            ("diclofenaco", "INVIMA-SIM-0010", "Diclofenaco", "Voltaren", "50 mg", "Caja x 20 tabletas", CondicionVenta.RX, False, "Tomar 1 tableta cada 12 horas con alimentos.", "1 caja", 10),
            ("atorvastatina", "INVIMA-SIM-0011", "Atorvastatina", "Lipitor", "20 mg", "Caja x 30 tabletas", CondicionVenta.RX, False, "Tomar 1 tableta cada 24 horas en la noche.", "3 cajas", 90),
            ("salbutamol", "INVIMA-SIM-0012", "Salbutamol", "Ventolin", "100 mcg/dosis", "Inhalador x 200 dosis", CondicionVenta.RX, False, "2 inhalaciones cada 6 a 8 horas si hay dificultad respiratoria.", "1 inhalador", 30),
            ("enalapril", "INVIMA-SIM-0013", "Enalapril", "Renitec", "10 mg", "Caja x 30 tabletas", CondicionVenta.RX, False, "Tomar 1 tableta cada 12 horas.", "2 cajas", 60),
            ("clonazepam", "INVIMA-SIM-0014", "Clonazepam", "Rivotril", "2 mg", "Caja x 30 tabletas", CondicionVenta.RX, True, "Tomar 1 tableta en la noche, unicamente bajo supervision medica.", "1 caja", 30),
            ("morfina", "INVIMA-SIM-0015", "Morfina", "MST Continus", "30 mg", "Caja x 20 tabletas", CondicionVenta.RX, True, "Tomar segun indicacion estricta y exclusiva del medico tratante.", "1 caja", 15),
            ("diazepam", "INVIMA-SIM-0016", "Diazepam", "Valium", "10 mg", "Caja x 20 tabletas", CondicionVenta.RX, True, "Tomar 1 tableta cada 12 horas, uso estrictamente controlado.", "1 caja", 15),
            ("vitamina_c", "INVIMA-SIM-0017", "Acido ascorbico", "Redoxon", "1 g", "Tubo x 10 tabletas efervescentes", CondicionVenta.OTC, False, "Disolver 1 tableta en agua cada 24 horas.", "2 tubos", 20),
            ("complejo_b", "INVIMA-SIM-0018", "Complejo B", "Bedoyecta", "Multivitaminico", "Caja x 30 tabletas", CondicionVenta.OTC, False, "Tomar 1 tableta cada 24 horas.", "1 caja", 30),
            ("azitromicina", "INVIMA-SIM-0019", "Azitromicina", "Zithromax", "500 mg", "Caja x 3 tabletas", CondicionVenta.RX, False, "Tomar 1 tableta cada 24 horas durante 3 dias completos.", "1 caja", 3),
            ("insulina_glargina", "INVIMA-SIM-0020", "Insulina glargina", "Lantus", "100 U/mL", "Vial x 10 mL", CondicionVenta.RX, False, "Aplicar via subcutanea segun indicacion medica, cada 24 horas.", "1 vial", 30),
        ]
        medicamentos = {
            clave: obtener_o_crear(
                db,
                Medicamento,
                registro_sanitario=registro,
                defaults={
                    "nombre_generico": generico,
                    "nombre_comercial": comercial,
                    "dosis": dosis,
                    "presentacion": presentacion,
                    "condicion_venta": condicion,
                    "control_especial": control_especial,
                    "indicaciones_uso": indicaciones,
                    "cantidad_por_entrega": cantidad_entrega,
                    "duracion_tratamiento_dias": duracion_dias,
                },
            )
            for clave, registro, generico, comercial, dosis, presentacion, condicion, control_especial, indicaciones, cantidad_entrega, duracion_dias in catalogo
        }
        db.commit()
        # Los objetos de `medicamentos` se van a usar mas abajo, ya con
        # `db` cerrada. Si accedemos a `medicamento.id` en ese punto,
        # SQLAlchemy intenta recargar el atributo (quedo "expirado" tras el
        # commit) y como la sesion ya esta cerrada, revienta con
        # DetachedInstanceError. Por eso guardamos los IDs en un dict de
        # Python normal *mientras la sesion sigue abierta*, y usamos ese
        # dict (no los objetos ORM) en el resto de la funcion.
        medicamento_ids = {clave: obj.id for clave, obj in medicamentos.items()}
        # Keep the connection metadata loaded after closing the central session.
        db.refresh(ips_1)
        db.refresh(ips_2)
        db.refresh(ips_3)
        crear_tablas_ips_registradas([ips_1, ips_2, ips_3])
    finally:
        db.close()

    # Each block writes only to that IPS's independent database.
    # Alcance actual del proyecto: solo Bogota. Se dejan 10 puntos repartidos
    # geograficamente por la ciudad (Chapinero, Rosales, Kennedy, Usaquen,
    # Teusaquillo, Suba, Engativa, Fontibon, Puente Aranda, Ciudad Bolivar)
    # con coordenadas reales de cada zona, para que el calculo de "punto mas
    # cercano" tenga sentido geografico de verdad en la demo. Antes habia
    # puntos sueltos en Medellin y Cali (uno cada uno) que se quitaron a
    # proposito: con un solo punto por ciudad la demo no mostraba nada
    # interesante, y el foco actual del proyecto es Bogota.
    with ips_session(ips_1) as db_ips:
        p1 = obtener_o_crear(db_ips, PuntoVenta, nombre="FarmaCentro Chapinero", defaults={"ciudad": "Bogota", "direccion": "Cra 13 #60-20", "lat": 4.6486, "lng": -74.0625})
        p2 = obtener_o_crear(db_ips, PuntoVenta, nombre="FarmaCentro Kennedy", defaults={"ciudad": "Bogota", "direccion": "Av. Ciudad de Cali #38-10 Sur", "lat": 4.6280, "lng": -74.1567})
        p3 = obtener_o_crear(db_ips, PuntoVenta, nombre="FarmaCentro Rosales", defaults={"ciudad": "Bogota", "direccion": "Cra 7 #72-30", "lat": 4.6640, "lng": -74.0540})
        p4 = obtener_o_crear(db_ips, PuntoVenta, nombre="FarmaCentro Usaquen", defaults={"ciudad": "Bogota", "direccion": "Cra 7 #119-30", "lat": 4.6946, "lng": -74.0305})
        for punto, medicamento_id, cantidad, fecha in [
            (p1, medicamento_ids["acetaminofen"], 50, None),
            (p1, medicamento_ids["losartan"], 0, date.today() + timedelta(days=5)),
            (p1, medicamento_ids["tramadol"], 10, None),
            (p2, medicamento_ids["acetaminofen"], 0, date.today() + timedelta(days=3)),
            (p2, medicamento_ids["losartan"], 12, None),
            (p3, medicamento_ids["acetaminofen"], 18, None),
            (p3, medicamento_ids["tramadol"], 6, None),
            (p4, medicamento_ids["losartan"], 9, None),
        ]:
            obtener_o_crear(db_ips, Inventario, punto_id=punto.id, medicamento_id=medicamento_id, defaults={"cantidad": cantidad, "fecha_reabastecimiento": fecha})
        historia = obtener_o_crear(db_ips, HistoriaClinica, cedula="1011097239", defaults={"diagnostico_simulado": "Hipertension arterial controlada"})
        obtener_o_crear(db_ips, PrescripcionActiva, historia_id=historia.id, medicamento_id=medicamento_ids["losartan"], defaults={"fecha_formula": date.today() - timedelta(days=10), "vigente": True})
        db_ips.commit()
    with ips_session(ips_2) as db_ips:
        p5 = obtener_o_crear(db_ips, PuntoVenta, nombre="VitalDrogas Suba", defaults={"ciudad": "Bogota", "direccion": "Cra 91 #146-30", "lat": 4.7480, "lng": -74.0930})
        p6 = obtener_o_crear(db_ips, PuntoVenta, nombre="VitalDrogas Teusaquillo", defaults={"ciudad": "Bogota", "direccion": "Cra 24 #39-51", "lat": 4.6320, "lng": -74.0910})
        p7 = obtener_o_crear(db_ips, PuntoVenta, nombre="VitalDrogas Engativa", defaults={"ciudad": "Bogota", "direccion": "Cll 68 #91-30", "lat": 4.7112, "lng": -74.1170})
        for punto, medicamento_id, cantidad, fecha in [
            (p5, medicamento_ids["acetaminofen"], 20, None),
            (p5, medicamento_ids["losartan"], 15, None),
            (p6, medicamento_ids["acetaminofen"], 8, None),
            (p6, medicamento_ids["tramadol"], 4, None),
            (p7, medicamento_ids["losartan"], 0, date.today() + timedelta(days=7)),
        ]:
            obtener_o_crear(db_ips, Inventario, punto_id=punto.id, medicamento_id=medicamento_id, defaults={"cantidad": cantidad, "fecha_reabastecimiento": fecha})
        db_ips.commit()
    with ips_session(ips_3) as db_ips:
        p8 = obtener_o_crear(db_ips, PuntoVenta, nombre="DrogaYa Fontibon", defaults={"ciudad": "Bogota", "direccion": "Cll 22 #96-15", "lat": 4.6675, "lng": -74.1469})
        p9 = obtener_o_crear(db_ips, PuntoVenta, nombre="DrogaYa Puente Aranda", defaults={"ciudad": "Bogota", "direccion": "Cra 50 #12-40", "lat": 4.6157, "lng": -74.1160})
        p10 = obtener_o_crear(db_ips, PuntoVenta, nombre="DrogaYa Ciudad Bolivar", defaults={"ciudad": "Bogota", "direccion": "Cll 70 Sur #18-25", "lat": 4.5709, "lng": -74.1646})
        for punto, medicamento_id, cantidad, fecha in [
            (p8, medicamento_ids["acetaminofen"], 12, None),
            (p9, medicamento_ids["acetaminofen"], 25, None),
            (p9, medicamento_ids["losartan"], 5, None),
            (p10, medicamento_ids["acetaminofen"], 0, date.today() + timedelta(days=2)),
        ]:
            obtener_o_crear(db_ips, Inventario, punto_id=punto.id, medicamento_id=medicamento_id, defaults={"cantidad": cantidad, "fecha_reabastecimiento": fecha})
        db_ips.commit()
    print("Datos demo cargados: base central y tres IPS independientes (10 puntos, todos en Bogota).")


if __name__ == "__main__":
    cargar()
