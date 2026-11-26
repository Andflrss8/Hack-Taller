from dotenv import load_dotenv
from google import genai

load_dotenv()

cliente = genai.Client()

model_id = "gemini-3.8-flash"

response = cliente.models.generate_content(
    model = model_id,
    contents = "En que batalla famosa Japon ataco una isla de EEUU en el Pacifico provocando que este entrara a la 2GM?"
)

print(f"RESPUESTA: {model_id} ")
print(response.text)