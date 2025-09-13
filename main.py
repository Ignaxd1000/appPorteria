import json
import os
import requests
from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from threading import Thread
import cv2
from pyzbar import pyzbar
import io
from kivy.core.image import Image as CoreImage

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"api_url": "http://localhost/api29-main/alumnos"}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

KV = '''
<RootWidget>:
    orientation: "vertical"
    padding: 30
    spacing: 16

    Label:
        text: "Configuración de URL de la API"
        font_size: 22
        size_hint_y: None
        height: 40

    TextInput:
        id: api_url_input
        text: root.api_url
        multiline: False
        size_hint_y: None
        height: 40

    Button:
        text: "Guardar URL de API"
        size_hint_y: None
        height: 40
        on_release: root.save_url(api_url_input.text)

    Label:
        text: "Escanear QR de Alumno / Ingresar Token"
        font_size: 18
        size_hint_y: None
        height: 30

    BoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: 40
        TextInput:
            id: input_token
            hint_text: "Pega el token aquí o escanea"
            multiline: False
        Button:
            text: "Escanear QR"
            size_hint_x: None
            width: 130
            on_release: root.start_qr_scan()

    Button:
        text: "Consultar Token"
        size_hint_y: None
        height: 40
        on_release: root.check_token(input_token.text)

    Label:
        id: result_label
        text: root.result_message
        font_size: 16
        color: (0,0.7,0,1) if root.result_ok else (1,0,0,1)
        size_hint_y: None
        height: self.texture_size[1] + 10

    BoxLayout:
        size_hint_y: None
        height: 120
        spacing: 10
        Image:
            id: alum_photo
            source: root.photo_url
            size_hint: None, None
            size: (100, 100)
            allow_stretch: True
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: 100
            Label:
                text: "Nombre: " + root.alum_name
                font_size: 16
                halign: "left"
                valign: "middle"
                text_size: self.size
            Label:
                text: "DNI: " + root.alum_dni
                font_size: 16
                halign: "left"
                valign: "middle"
                text_size: self.size
'''

class RootWidget(BoxLayout):
    api_url = StringProperty()
    result_message = StringProperty()
    result_ok = BooleanProperty(False)
    alum_name = StringProperty("")
    alum_dni = StringProperty("")
    photo_url = StringProperty("")
    last_token = StringProperty("")
    last_legajo = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        config = load_config()
        self.api_url = config.get("api_url", "")
        self.result_message = ""
        self.alum_name = ""
        self.alum_dni = ""
        self.photo_url = ""
        self.last_token = ""
        self.last_legajo = ""

    def save_url(self, url):
        url = url.strip()
        if url:
            save_config({"api_url": url})
            self.api_url = url
            self.result_message = "URL guardada correctamente."
            self.result_ok = True
        else:
            self.result_message = "¡La URL no puede estar vacía!"
            self.result_ok = False

    def check_token(self, token):
        token = token.strip()
        self.alum_name = ""
        self.alum_dni = ""
        self.photo_url = ""
        self.last_token = ""
        self.last_legajo = ""
        if not token:
            self.result_message = "Por favor ingrese un token."
            self.result_ok = False
            return
        url = self.api_url
        if not url:
            self.result_message = "Primero configure la URL de la API."
            self.result_ok = False
            return
        try:
            response = requests.post(url, json={"token": token}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print("DATA:", data)  # Para debug
                alumno = None
                if "alumno" in data:
                    alumno = data["alumno"]
                elif "detalle" in data and isinstance(data["detalle"], dict) and "alumno" in data["detalle"]:
                    alumno = data["detalle"]["alumno"]
                if alumno:
                    self.alum_name = str(alumno.get("nombres", ""))
                    self.alum_dni = str(alumno.get("dni", ""))
                    legajo = alumno.get("legajo", "")
                    self.last_token = token
                    self.last_legajo = str(legajo)
                    foto_url = alumno.get("foto", "")
                    # Construir URL absoluta si es necesario
                    if not foto_url and legajo:
                        base = url.split("/alumnos")[0]
                        foto_url = f"{base}/alumnos/foto/{legajo}?token={token}"
                    elif foto_url and not foto_url.startswith("http"):
                        base = url.split("/alumnos")[0]
                        foto_url = f"{base}/{foto_url.lstrip('/')}"
                    print("URL FINAL FOTO:", foto_url)
                    self.set_photo_from_url(foto_url)
                    self.result_message = f"¡Token válido! Alumno encontrado."
                    self.result_ok = True
                else:
                    self.result_message = "Token no pertenece a ningún alumno."
                    self.result_ok = False
            else:
                try:
                    err = response.json()
                    self.result_message = f"Error en la API: {err.get('detalle', response.text)}"
                except Exception:
                    self.result_message = f"Error en la API: {response.status_code}"
                self.result_ok = False
        except requests.RequestException as e:
            self.result_message = f"Error de conexión: {e}"
            self.result_ok = False

    def set_photo_from_url(self, url):
        self.photo_url = ""  # Limpia la imagen previa
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = io.BytesIO(r.content)
                image = CoreImage(data, ext="jpg")
                self.ids.alum_photo.texture = image.texture
                self.result_message += " [Foto cargada]"
            else:
                self.result_message += " [No se pudo cargar foto]"
        except Exception as e:
            self.result_message += f" [Error foto: {e}]"

    def start_qr_scan(self):
        self.result_message = "Abriendo cámara para escanear QR..."
        self.result_ok = True
        Thread(target=self._scan_qr_thread, daemon=True).start()

    def _scan_qr_thread(self):
        cap = cv2.VideoCapture(0)
        found = False
        while cap.isOpened() and not found:
            ret, frame = cap.read()
            if not ret:
                continue
            decoded_objs = pyzbar.decode(frame)
            for obj in decoded_objs:
                token = obj.data.decode("utf-8")
                found = True
                def _set_token():
                    self.ids.input_token.text = token
                    self.result_message = "QR escaneado correctamente."
                    self.result_ok = True
                Clock.schedule_once(lambda dt: _set_token())
                break
            cv2.imshow("Escanee el QR y cierre la ventana cuando termine (ESC)", frame)
            if cv2.waitKey(1) == 27:
                break
        cap.release()
        cv2.destroyAllWindows()

class AppPorteria(App):
    def build(self):
        Builder.load_string(KV)
        return RootWidget()

if __name__ == "__main__":
    AppPorteria().run()