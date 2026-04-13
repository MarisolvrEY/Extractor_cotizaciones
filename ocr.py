# test_ocr.py — crea este archivo en la raíz del proyecto y córrelo
import requests
from config import settings

url = (
    f"{settings.AZURE_OCR_ENDPOINT.rstrip('/')}"
    f"/documentintelligence/documentModels/prebuilt-read:analyze"
    f"?api-version=2024-11-30"
)
headers = {"Ocp-Apim-Subscription-Key": settings.AZURE_OCR_KEY}
payload = {"urlSource": "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/sample-layout.pdf"}

print("URL:", url)
print("KEY (primeros 6):", settings.AZURE_OCR_KEY[:6])

resp = requests.post(url, headers=headers, json=payload, timeout=30)
print("Status:", resp.status_code)
print("Response:", resp.text[:500])