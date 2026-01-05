from ursina import *
import random
import threading
import winsound
import time

# --- 1. CONFIGURACIÓN INICIAL ---
app = Ursina()
window.title = "RUBIK"
window.borderless = False
window.color = color.rgb(25, 25, 25) # Gris oscuro elegante
window.fps_counter.enabled = False 

# --- 2. SISTEMA DE SONIDO ---
def play_sound(tipo):
    def _run():
        try:
            if tipo == 'click': winsound.Beep(700, 30)
            if tipo == 'win': 
                for i in range(3): winsound.Beep(800+(i*100), 80)
        except: pass
    threading.Thread(target=_run).start()

# --- 3. ESCENARIO ---
camera.position = (0, 0, -22)
EditorCamera()
AmbientLight(color=color.rgb(120, 120, 120))
PointLight(parent=camera, position=(0,0,-5), color=color.white)

# --- 4. INTERFAZ (UI) CORREGIDA ---
# Panel lateral más ancho y ordenado
panel = Entity(parent=camera.ui, model='quad', scale=(0.6, 1), position=(-0.70, 0), color=color.rgba(0, 0, 0, 0.9))

# Título
Text(text='RUBIK', position=(-0.82, 0.45), scale=2, color=color.cyan)

# Sección Estado
Text(text='ESTADO:', position=(-0.82, 0.35), scale=1, color=color.gray)
ui_estado = Text(text='LISTO', position=(-0.82, 0.30), scale=1.5, color=color.white)

# Sección Cola (Movimientos pendientes)
Text(text='COLA:', position=(-0.82, 0.20), scale=1, color=color.gray)
ui_cola = Text(text='0', position=(-0.82, 0.15), scale=1.5, color=color.white)

# Sección Movimientos Realizados
Text(text='MOVS:', position=(-0.82, 0.05), scale=1, color=color.gray)
ui_movs = Text(text='0', position=(-0.82, 0.00), scale=1.5, color=color.white)

# Controles (Abajo del todo para no molestar)
Text(text='CONTROLES', position=(-0.82, -0.25), scale=0.8, color=color.cyan)
Text(text='[ESPACIO] Mezclar\n[ENTER] Resolver Auto\n[W,A,S,D,Q,E] Girar', position=(-0.82, -0.30), scale=0.75, color=color.light_gray)

# --- 5. LÓGICA DEL MOTOR ---
cubos = []
pivote = Entity()
esta_animando = False # SEMÁFORO PRINCIPAL

# Listas de datos
historial_usuario = [] # Lo que tú haces (para poder deshacerlo)
cola_pendientes = []   # La lista de tareas para la IA

colores = {
    'R': color.red, 'L': color.orange, 'U': color.white,
    'D': color.yellow, 'F': color.green, 'B': color.azure
}

def crear_cubo():
    for c in cubos: destroy(c)
    cubos.clear()
    pivote.rotation = (0,0,0)
    
    for x in range(3):
        for y in range(3):
            for z in range(3):
                pieza = Entity(model='cube', color=color.black, scale=0.98, position=(x-1, y-1, z-1))
                g, t, d = 0.05, 0.90, 0.501
                if x == 2: Entity(parent=pieza, model='cube', color=colores['R'], scale=(g,t,t), x=d)
                if x == 0: Entity(parent=pieza, model='cube', color=colores['L'], scale=(g,t,t), x=-d)
                if y == 2: Entity(parent=pieza, model='cube', color=colores['U'], scale=(t,g,t), y=d)
                if y == 0: Entity(parent=pieza, model='cube', color=colores['D'], scale=(t,g,t), y=-d)
                if z == 2: Entity(parent=pieza, model='cube', color=colores['F'], scale=(t,t,g), z=d)
                if z == 0: Entity(parent=pieza, model='cube', color=colores['B'], scale=(t,t,g), z=-d)
                cubos.append(pieza)
crear_cubo()

# --- 6. FÍSICA Y ANIMACIÓN ---

def finalizar_animacion():
    """Se ejecuta EXACTAMENTE cuando termina el giro visual"""
    global esta_animando
    
    # 1. Soltar piezas del pivote
    for c in cubos:
        c.world_parent = scene
        # 2. GRID SNAP (Alineación forzosa a la rejilla)
        c.position = (round(c.x), round(c.y), round(c.z))
        c.rotation = (round(c.rotation_x/90)*90, round(c.rotation_y/90)*90, round(c.rotation_z/90)*90)
    
    # 3. Resetear pivote
    pivote.rotation = (0,0,0)
    
    # 4. Abrir semáforo
    esta_animando = False

def ejecutar_giro_fisico(lado, sentido, velocidad):
    global esta_animando
    esta_animando = True
    play_sound('click')

    # Seleccionar piezas
    grupo = []
    for c in cubos:
        if lado == 'R' and round(c.x) == 1: grupo.append(c)
        if lado == 'L' and round(c.x) == -1: grupo.append(c)
        if lado == 'U' and round(c.y) == 1: grupo.append(c)
        if lado == 'D' and round(c.y) == -1: grupo.append(c)
        if lado == 'F' and round(c.z) == 1: grupo.append(c)
        if lado == 'B' and round(c.z) == -1: grupo.append(c)

    # Unir al pivote
    for c in grupo: c.world_parent = pivote
    
    # Calcular grados
    eje = 'x' if lado in 'RL' else ('y' if lado in 'UD' else 'z')
    grados = 90 * sentido
    if lado in 'LDB': grados *= -1
    
    # Animar
    pivote.animate(f'rotation_{eje}', grados, duration=velocidad, curve=curve.in_out_quad)
    
    # Programar el final OBLIGATORIO
    invoke(finalizar_animacion, delay=velocidad + 0.05)

# --- 7. EL CEREBRO (GESTOR DE COLAS) ---

def agregar_accion(lado, sentido, velocidad, es_usuario):
    """Añade una orden a la cola de espera"""
    cola_pendientes.append({
        'lado': lado,
        'sentido': sentido,
        'vel': velocidad,
        'es_user': es_usuario
    })

def update():
    # Actualizar textos UI
    ui_cola.text = str(len(cola_pendientes))
    
    # LÓGICA DE PROCESAMIENTO
    # Solo si el semáforo está verde (False) Y hay cosas en la cola
    if not esta_animando and len(cola_pendientes) > 0:
        
        # Sacar la siguiente tarea
        tarea = cola_pendientes.pop(0)
        
        # Actualizar contadores
        if tarea['es_user']:
            historial_usuario.append((tarea['lado'], tarea['sentido']))
            ui_movs.text = str(len(historial_usuario))
        
        # Ejecutar físicamente
        ejecutar_giro_fisico(tarea['lado'], tarea['sentido'], tarea['vel'])
        
        # Verificar si terminamos de resolver
        if len(cola_pendientes) == 0 and ui_estado.text == 'RESOLVIENDO':
            ui_estado.text = 'RESUELTO'
            ui_estado.color = color.green
            play_sound('win')

# --- 8. FUNCIONES DE CONTROL ---

def mezclar():
    if len(cola_pendientes) > 0: return # No interrumpir
    
    historial_usuario.clear() # Olvidar historial viejo
    ui_movs.text = '0'
    ui_estado.text = 'MEZCLANDO'
    ui_estado.color = color.orange
    
    lados = ['R', 'L', 'U', 'D', 'F', 'B']
    for _ in range(15):
        # Velocidad 0.1s es segura con este sistema
        agregar_accion(random.choice(lados), random.choice([1, -1]), 0.1, True)
    
    # Al terminar la mezcla, cambiar texto
    def volver_listo():
        if ui_estado.text == 'MEZCLANDO': 
            ui_estado.text = 'LISTO'
            ui_estado.color = color.white
    invoke(volver_listo, delay=15 * 0.15 + 0.5)

def resolver_auto():
    if len(historial_usuario) == 0: return
    if len(cola_pendientes) > 0: return # Esperar a que esté quieto
    
    ui_estado.text = 'RESOLVIENDO'
    ui_estado.color = color.cyan
    
    # Invertir la historia
    pasos_inversos = list(reversed(historial_usuario))
    historial_usuario.clear()
    ui_movs.text = '0'
    
    for paso in pasos_inversos:
        lado, sentido_original = paso
        # Sentido inverso y velocidad media (0.2s) para que se aprecie
        agregar_accion(lado, sentido_original * -1, 0.2, False)

def input(key):
    # Controles de usuario (van a la cola también, para evitar choques)
    if key == 'd': agregar_accion('R', 1, 0.25, True)
    if key == 'a': agregar_accion('L', 1, 0.25, True)
    if key == 'w': agregar_accion('U', 1, 0.25, True)
    if key == 's': agregar_accion('D', 1, 0.25, True)
    if key == 'e': agregar_accion('F', 1, 0.25, True)
    if key == 'q': agregar_accion('B', 1, 0.25, True)
    
    if key == 'space': mezclar()
    if key == 'enter': resolver_auto()

app.run()