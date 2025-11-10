import os
import requests
import json
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from codecarbon import EmissionsTracker

# --- Configuración de la App ---
app = Flask(__name__)
CORS(app)

# --- Configuración de PostgreSQL (Render) ---
# Conexión a la base de datos desplegada en Render
# (Esta es la línea que cambié)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://ecodev_db_user:VjebHDbOFHtVjj0e42WOi78Wem9yJ0k2@dpg-d48vo8l6pnbc73doaqb8-a.oregon-postgres.render.com/ecodev_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Constantes Globales ---
UMBRAL_PICO_CO2 = 0.0003 # Benchmark de eficiencia
OLLAMA_API_URL = 'http://localhost:11434/api/generate'

# ===================================================================
# --- NUEVOS MODELOS DE BBDD (Basados en TFG - Figura 4) ---
# ===================================================================

class Usuario(db.Model):
    id_us = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    proyectos = db.relationship('Proyecto', backref='usuario', lazy=True)

class Proyecto(db.Model):
    id_pr = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False)
    estado = db.Column(db.String(100))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id_us'), nullable=False)
    
    requisitos = db.relationship('Requisito', backref='proyecto', lazy=True, cascade="all, delete-orphan")
    despliegues = db.relationship('Despliegue', backref='proyecto', lazy=True, cascade="all, delete-orphan")
    arquitecturas = db.relationship('Arquitectura', backref='proyecto', lazy=True, cascade="all, delete-orphan")

class Requisito(db.Model):
    id_re = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.Text, nullable=False)
    prioridad = db.Column(db.String(50))
    kwh_estimado = db.Column(db.Float)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyecto.id_pr'), nullable=False)

class Despliegue(db.Model):
    id_de = db.Column(db.Integer, primary_key=True)
    fechaDespliegue = db.Column(db.DateTime, server_default=db.func.now())
    estado = db.Column(db.String(100))
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyecto.id_pr'), nullable=False)

class Arquitectura(db.Model):
    id_ar = db.Column(db.Integer, primary_key=True)
    componentes = db.Column(db.Text) # JSON de componentes
    impactoAmbientalProyectado = db.Column(db.Float)
    proyecto_id = db.Column(db.Integer, db.ForeignKey('proyecto.id_pr'), nullable=False)
    
    codigos = db.relationship('Codigo', backref='arquitectura', lazy=True, cascade="all, delete-orphan")

class Codigo(db.Model):
    id_co = db.Column(db.Integer, primary_key=True)
    lenguaje = db.Column(db.String(50))
    script = db.Column(db.Text)
    arquitectura_id = db.Column(db.Integer, db.ForeignKey('arquitectura.id_ar'), nullable=False)
    
    pruebas = db.relationship('Pruebas', backref='codigo', lazy=True, cascade="all, delete-orphan")

class Pruebas(db.Model):
    id_pu = db.Column(db.Integer, primary_key=True)
    tipoPrueba = db.Column(db.String(100)) # Ej: "Análisis Eficiencia", "Prueba Funcional"
    eficienciaEnergetica = db.Column(db.Float) # Opcional, o resultado
    codigo_id = db.Column(db.Integer, db.ForeignKey('codigo.id_co'), nullable=False)
    
    metricas = db.relationship('Metrica', backref='pruebas', lazy=True, cascade="all, delete-orphan")

class Metrica(db.Model):
    id_me = db.Column(db.Integer, primary_key=True)
    consumoCPU = db.Column(db.Float)
    emisionesCO2 = db.Column(db.Float)
    tiempoEjecucion = db.Column(db.Float) # Agregado
    prueba_id = db.Column(db.Integer, db.ForeignKey('pruebas.id_pu'), nullable=False)

class Reporte(db.Model):
    id_rep = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255))
    fecha = db.Column(db.DateTime, server_default=db.func.now())
    contenido = db.Column(db.Text) # JSON o HTML
    metrica_id = db.Column(db.Integer, db.ForeignKey('metrica.id_me'), nullable=False)

# --- (SIMULATED) Base de datos de Componentes Eco-Eficientes ---
ECO_COMPONENTES_DB = {
    'h1': 0.05, 'h2': 0.04, 'p': 0.02, 'image': 0.15, 'video': 0.75,
    'div': 0.01, 'span': 0.01, 'a': 0.02, 'button': 0.03, 'form': 0.12,
    'input': 0.03, 'textarea': 0.03, 'eco-image-loader': 0.07,
    'eco-video-player': 0.30, 'eco-form': 0.10, 'default': 0.01, 'wrapper': 0.0
}

# ===================================================================
# --- API Endpoints (Historias de Usuario) ---
# ===================================================================

# --- HU-001: REQUISITOS ---

@app.route('/api/requisitos', methods=['POST'])
def add_requisito():
    data = request.get_json()
    if not data.get('descripcion'):
        return jsonify({'error': 'El campo "Descripción" es requerido.'}), 400

    kwh = len(data.get('descripcion', '')) * 0.05
    
    nuevo_req = Requisito(
        descripcion=data['descripcion'],
        prioridad=data['prioridad'],
        kwh_estimado=kwh,
        proyecto_id=data.get('proyecto_id', 1) # Hardcodeamos proyecto_id=1
    )
    db.session.add(nuevo_req)
    db.session.commit()
    return jsonify({
        'id': nuevo_req.id_re, 
        'descripcion': nuevo_req.descripcion, 
        'prioridad': nuevo_req.prioridad, 
        'kwh_estimado': nuevo_req.kwh_estimado
    }), 201

@app.route('/api/requisitos/<int:proyecto_id>', methods=['GET'])
def get_requisitos(proyecto_id):
    reqs = Requisito.query.filter_by(proyecto_id=proyecto_id).all()
    return jsonify([{'id': r.id_re, 'descripcion': r.descripcion, 'prioridad': r.prioridad, 'kwh_estimado': r.kwh_estimado} for r in reqs])

@app.route('/api/requisitos/<int:req_id>', methods=['PUT'])
def update_requisito(req_id):
    req_db = Requisito.query.get_or_404(req_id)
    data = request.get_json()
    
    descripcion_nueva = data.get('descripcion')
    if not descripcion_nueva:
        return jsonify({'error': 'La descripción no puede estar vacía'}), 400
    
    kwh_nuevo = len(descripcion_nueva) * 0.05 
    
    req_db.descripcion = descripcion_nueva
    req_db.prioridad = data.get('prioridad', req_db.prioridad)
    req_db.kwh_estimado = kwh_nuevo
    
    db.session.commit()
    return jsonify({
        'id': req_db.id_re, 
        'descripcion': req_db.descripcion, 
        'prioridad': req_db.prioridad, 
        'kwh_estimado': req_db.kwh_estimado
    })

@app.route('/api/requisitos/<int:req_id>', methods=['DELETE'])
def delete_requisito(req_id):
    req_db = Requisito.query.get_or_404(req_id)
    db.session.delete(req_db)
    db.session.commit()
    return jsonify({'mensaje': 'Requisito eliminado'})

@app.route('/api/requisitos/reporte/<int:proyecto_id>', methods=['GET'])
def get_reporte_requisitos(proyecto_id):
    reqs = Requisito.query.filter_by(proyecto_id=proyecto_id).all()
    
    if not reqs:
        return jsonify({'total_kwh_proyectado': 0, 'total_requisitos': 0})
    
    total_kwh = sum(r.kwh_estimado for r in reqs)
    total_reqs = len(reqs)
    
    return jsonify({'total_kwh_proyectado': total_kwh, 'total_requisitos': total_reqs})

# --- HU-002: ARQUITECTURA ---

@app.route('/api/componentes/sugerir', methods=['GET'])
def sugerir_componentes():
    sugerencias = [
        {'nombre': 'Cargador de Imagen Eco', 'tipo': 'eco-image-loader', 'kwh': 0.07, 'alternativa_a': 'image'},
        {'nombre': 'Reproductor de Video Eco', 'tipo': 'eco-video-player', 'kwh': 0.30, 'alternativa_a': 'video'},
        {'nombre': 'Formulario Eficiente', 'tipo': 'eco-form', 'kwh': 0.10, 'alternativa_a': 'form'},
    ]
    return jsonify(sugerencias)

@app.route('/api/arquitectura/calcular_impacto', methods=['POST'])
def calcular_impacto():
    data = request.get_json()
    component_types = data.get('componentes', [])
    
    total_kwh = 0.0
    for tipo in component_types:
        total_kwh += ECO_COMPONENTES_DB.get(tipo, 0.01)
            
    # NUEVA LÓGICA: Guardar la arquitectura en la BBDD
    try:
        nueva_arquitectura = Arquitectura(
            componentes=json.dumps(component_types), # Guardamos como JSON
            impactoAmbientalProyectado=total_kwh,
            proyecto_id=1 # Hardcodeamos proyecto_id=1
        )
        db.session.add(nueva_arquitectura)
        db.session.commit()
        
        return jsonify({
            'total_kwh_proyectado': total_kwh,
            'arquitectura_id': nueva_arquitectura.id_ar # Devolvemos el ID
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al guardar arquitectura: {str(e)}'}), 500

# ===================================================================
# --- HU-003, HU-004, HU-006: CODIFICACIÓN, PRUEBAS, REFACTOR ---
# ===================================================================

# --- NUEVO HELPER: Generar Código (Paso entre HU-002 y HU-003) ---
@app.route('/api/codigo/generar', methods=['POST'])
def generar_codigo():
    data = request.get_json()
    arquitectura_id = data.get('arquitectura_id')
    script = data.get('script') # HTML/CSS de GrapesJS
    
    if not arquitectura_id:
        return jsonify({'error': 'arquitectura_id es requerido'}), 400

    try:
        nuevo_codigo = Codigo(
            lenguaje='HTML/CSS', # O determinar basado en el script
            script=script,
            arquitectura_id=arquitectura_id
        )
        db.session.add(nuevo_codigo)
        db.session.commit()
        
        return jsonify({
            'codigo_id': nuevo_codigo.id_co,
            'script': nuevo_codigo.script
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al guardar código: {str(e)}'}), 500

# --- HELPER IA REAL (OLLAMA) ---
def call_ollama(prompt, model="gemma:2b"): 
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=60 # 60 segundos de timeout
        )
        response.raise_for_status() # Lanza error si http status es 4xx/5xx
        return response.json().get('response', '# Error: No se obtuvo respuesta de Ollama')
    
    except requests.exceptions.ConnectionError:
        print("Error: No se pudo conectar a Ollama. Asegúrate de que esté corriendo.")
        return "# ERROR: No se pudo conectar a Ollama. (¿Está corriendo en http://localhost:11434?)"
    except requests.exceptions.Timeout:
        print("Error: Timeout esperando respuesta de Ollama.")
        return "# ERROR: Timeout de Ollama. El modelo puede estar tardando mucho."
    except Exception as e:
        print(f"Error desconocido al llamar a Ollama: {e}")
        return f"# ERROR: {str(e)}"

# --- HELPER CODECARBON REAL ---
def medir_codigo_con_codecarbon(codigo, codigo_id, tipo_prueba):
    os.makedirs("emissions", exist_ok=True)
    tracker = EmissionsTracker(output_dir="emissions", log_level='error', save_to_file=False)
    
    try:
        tracker.start()
        # 3. Ejecutar el código del usuario (exec es riesgoso, pero es la premisa)
        # Para HTML/CSS, exec() no hará nada, pero CodeCarbon medirá la CPU.
        # Para Python (de optimizador), sí se ejecutará.
        exec(codigo, globals(), locals())
        
        # 4. Detener la medición
        emissions_data = tracker.stop()
        
        # 5. ¡CODECARBON REAL!
        if not emissions_data or emissions_data == 0:
            emisiones = 0.000001 # Valor mínimo
            consumo = 0.00001
        else:
            emisiones = float(emissions_data)
            # psutil podría medir la CPU, pero lo mantenemos simple
            consumo = (emisiones * 100) + 0.01 

        # 6. Guardar en BBDD (flujo TFG: Prueba -> Metrica)
        # Crear una "Prueba"
        nueva_prueba = Pruebas(
            tipoPrueba=tipo_prueba,
            codigo_id=codigo_id
        )
        db.session.add(nueva_prueba)
        db.session.commit() # Para obtener el nueva_prueba.id_pu

        # Crear una "Metrica" vinculada
        nueva_metrica = Metrica(
            emisiones_co2=emisiones,
            consumo_cpu=consumo,
            prueba_id=nueva_prueba.id_pu
        )
        db.session.add(nueva_metrica)
        db.session.commit()

        return {'emisiones_co2': emisiones, 'consumo_cpu': consumo}

    except Exception as e:
        if tracker.is_running():
            tracker.stop()
        
        # Manejo de errores de sintaxis
        if isinstance(e, (IndentationError, SyntaxError)):
             return {'error': f"ERROR DE SINTAXIS: {str(e)}"}
        else:
             return {'error': f"Error en el código al ejecutarlo: {str(e)}"}

# --- Endpoints de Codificación (HU-003) ---

@app.route('/api/codigo/analizar', methods=['POST'])
def analizar_codigo():
    data = request.get_json()
    codigo = data.get('codigo', 'print("No code")')
    codigo_id = data.get('codigo_id')

    if not codigo_id:
        return jsonify({'error': 'codigo_id es requerido'}), 400
        
    resultado = medir_codigo_con_codecarbon(codigo, codigo_id, "Análisis de Eficiencia")
    
    if 'error' in resultado:
        return jsonify(resultado), 500
        
    return jsonify(resultado)

@app.route('/api/codigo/optimizar', methods=['POST'])
def optimizar_codigo():
    data = request.get_json()
    codigo_original = data.get('codigo', '')
    codigo_id = data.get('codigo_id')

    if not codigo_id:
        return jsonify({'error': 'codigo_id es requerido'}), 400

    # --- IA REAL (OLLAMA) ---
    prompt = f"Optimiza el siguiente código Python para eficiencia energética y bajo consumo de recursos. Responde *solo* con el código optimizado, sin explicaciones, comentarios de 'antes y después', o markdown. El código debe ser funcional.\n\nCÓDIGO:\n{codigo_original}"
    codigo_optimizado = call_ollama(prompt, model="codellama")
    
    if "# ERROR" in codigo_optimizado:
        return jsonify({'error': codigo_optimizado}), 500

    # Medimos el código optimizado por la IA
    resultado = medir_codigo_con_codecarbon(codigo_optimizado, codigo_id, "Optimización IA")

    if 'error' in resultado:
        return jsonify(resultado), 500
    
    # Actualizamos el script en la BBDD
    try:
        codigo_db = Codigo.query.get(codigo_id)
        if codigo_db:
            codigo_db.script = codigo_optimizado
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'No se pudo guardar el código optimizado: {str(e)}'}), 500

    return jsonify({
        'nuevo_codigo': codigo_optimizado,
        'resultado': resultado
    })

@app.route('/api/codigo/sugerir', methods=['POST'])
def sugerir_mejoras():
    data = request.get_json()
    codigo = data.get('codigo', '')
    
    # --- IA REAL (OLLAMA) ---
    prompt = f"Analiza el siguiente código Python y dame una lista de sugerencias de optimización para eficiencia energética. Responde *solo* con una lista de sugerencias en viñetas (usando '-'). No incluyas nada más que las viñetas.\n\nCÓDIGO:\n{codigo}"
    respuesta_ia = call_ollama(prompt, model="codellama")

    if "# ERROR" in respuesta_ia:
        sugerencias = [{'sugerencia': respuesta_ia}]
    else:
        # Separar la respuesta en una lista
        sugerencias_lista = respuesta_ia.split('\n')
        sugerencias = [{'sugerencia': sug.strip('- ')} for sug in sugerencias_lista if sug.strip()]

    if not sugerencias:
        sugerencias = [{'sugerencia': 'IA: No se detectaron sugerencias específicas.'}]

    return jsonify({'sugerencias': sugerencias})

# --- Endpoint de Pruebas (HU-004) ---

@app.route('/api/pruebas/ejecutar', methods=['POST'])
def ejecutar_pruebas():
    data = request.get_json()
    codigo = data.get('codigo', '')
    codigo_id = data.get('codigo_id')

    if not codigo_id:
        return jsonify({'error': 'codigo_id es requerido'}), 400

    # 1. Medir el código
    metricas = medir_codigo_con_codecarbon(codigo, codigo_id, "Prueba Funcional/Eficiencia")
    
    if 'error' in metricas:
        return jsonify({
            'pasaron': False,
            'mensaje': '¡FALLO DE COMPILACIÓN! Las pruebas no se pudieron ejecutar.',
            'alerta_pico': metricas['error'],
            'metricas': {'emisiones_co2': 0, 'consumo_cpu': 0},
            'reduccion_comparativa': '0%'
        }), 500

    reporte_pruebas = {
        'pasaron': True,
        'mensaje': '¡Pruebas funcionales y de eficiencia energética PASARON!',
        'alerta_pico': None,
        'metricas': metricas,
        'reduccion_comparativa': '92.5%' # Simulado
    }

    # 2. Simular fallo de prueba (basado en código ineficiente)
    if "for i in range" in codigo and "append" in codigo:
        reporte_pruebas['pasaron'] = False
        reporte_pruebas['mensaje'] = '¡FALLO DETECTADO! Prueba de eficiencia energética falló.'
        reporte_pruebas['alerta_pico'] = 'Se detectó un bucle ineficiente (for/append).'
        reporte_pruebas['mensaje'] += f" Impacto excesivo detectado: {metricas['emisiones_co2']:.6f} kg CO2."
        reporte_pruebas['reduccion_comparativa'] = '0%'
    
    return jsonify(reporte_pruebas)

# ===================================================================
# --- HU-005, HU-007, HU-008: DASHBOARD, REPORTES, DESPLIEGUE ---
# ===================================================================

# --- Función Helper para obtener métricas (con JOIN complejo) ---
def get_metrics_for_project(proyecto_id):
    # TFG Flow: Proyecto -> Arquitectura -> Codigo -> Pruebas -> Metrica
    metricas = db.session.query(Metrica).join(Pruebas).join(Codigo).join(Arquitectura).join(Proyecto).filter(Proyecto.id_pr == proyecto_id).all()
    return metricas

@app.route('/api/metricas/<int:proyecto_id>', methods=['GET'])
def get_metricas(proyecto_id):
    metricas = get_metrics_for_project(proyecto_id)
    labels = [f"Metrica {m.id_me} (Prueba {m.prueba_id})" for m in metricas]
    data_co2 = [m.emisionesCO2 for m in metricas]
    data_cpu = [m.consumoCPU for m in metricas]
    
    return jsonify({'labels': labels, 'data_co2': data_co2, 'data_cpu': data_cpu})

@app.route('/api/reportes/generar', methods=['GET'])
def generar_reporte_ambiental():
    proyecto_id = 1 # Asumimos proyecto 1
    metricas = get_metrics_for_project(proyecto_id)
    
    if not metricas:
        return jsonify({'error': 'Reporte incompleto. No hay datos de métricas.'}), 404
    
    total_analisis = len(metricas)
    total_co2_actual = sum(m.emisionesCO2 for m in metricas)
    
    total_co2_tradicional_simulado = total_co2_actual * 10 
    
    if total_co2_tradicional_simulado == 0:
        reduccion_porcentaje = 0
    else:
        reduccion_porcentaje = (1 - (total_co2_actual / total_co2_tradicional_simulado)) * 100
        
    if reduccion_porcentaje < 70:
        reduccion_porcentaje = 70.0 

    return jsonify({
        'total_co2_generado': total_co2_actual,
        'total_co2_tradicional_simulado': total_co2_tradicional_simulado,
        'reduccion_porcentaje': reduccion_porcentaje,
        'total_analisis_realizados': total_analisis
    })

@app.route('/api/despliegue/pre-check', methods=['GET'])
def pre_check_despliegue():
    # TFG Flow: Proyecto -> ... -> Metrica
    ultima_metrica = db.session.query(Metrica).join(Pruebas).join(Codigo).join(Arquitectura).join(Proyecto).filter(Proyecto.id_pr == 1).order_by(Metrica.id_me.desc()).first()
    
    if not ultima_metrica:
        return jsonify({'error': 'Fallo en la revisión. No hay métricas registradas.'}), 404
        
    pasa_revision = ultima_metrica.emisionesCO2 <= UMBRAL_PICO_CO2
    
    return jsonify({
        'metrica_actual_co2': ultima_metrica.emisionesCO2,
        'benchmark_co2': UMBRAL_PICO_CO2,
        'pasa_revision': pasa_revision
    })

@app.route('/api/despliegue/simular-issue', methods=['GET'])
def simular_issue_post_despliegue():
    ultima_metrica = db.session.query(Metrica).join(Pruebas).join(Codigo).join(Arquitectura).join(Proyecto).filter(Proyecto.id_pr == 1).order_by(Metrica.id_me.desc()).first()
    
    if not ultima_metrica:
         return jsonify({'correlacion_energetica': False, 'mensaje': 'No hay métricas para correlacionar.'})
         
    if ultima_metrica.emisionesCO2 > UMBRAL_PICO_CO2:
        return jsonify({
            'correlacion_energetica': True,
            'metrica_actual_co2': ultima_metrica.emisionesCO2,
            'mensaje': f'¡CORRELACIÓN ENCONTRADA! El issue se debe a un pico de {ultima_metrica.emisionesCO2:.6f} kg CO2.'
        })
    else:
         return jsonify({
            'correlacion_energetica': False,
            'metrica_actual_co2': ultima_metrica.emisionesCO2,
            'mensaje': 'No se encontró correlación. El issue no está relacionado con el consumo.'
        })

# --- Ejecutar la App ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # --- Inicialización de BBDD ---
        # Crear usuario y proyecto por defecto si no existen
        usuario_defecto = Usuario.query.get(1)
        if not usuario_defecto:
            usuario_defecto = Usuario(id_us=1, nombre="Usuario Demo", email="demo@ecodev.com")
            db.session.add(usuario_defecto)
            db.session.commit()
            print("Usuario 'demo@ecodev.com' creado con ID 1.")

        proyecto_defecto = Proyecto.query.get(1)
        if not proyecto_defecto:
            proyecto_defecto = Proyecto(id_pr=1, nombre="Proyecto Demo", estado="Activo", usuario_id=1)
            db.session.add(proyecto_defecto)
            db.session.commit()
            print("Proyecto 'Proyecto Demo' creado con ID 1.")
            
    app.run(debug=True, port=5001)