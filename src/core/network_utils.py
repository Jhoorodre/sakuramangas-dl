import os
import logging
from src.core.utils import is_valid_image


class ImageInterceptor:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.ordered_urls = []
        self.downloaded_files = {}
        self.drm_headers = {}

    def throttle_traffic(self, route):
        try:
            route.continue_()
        except Exception:
            pass

    def handle_response(self, response):
        if "/imagens/" in response.url and response.url.endswith(".jpg"):
            # Escuta Ativa (Sniffer): Captura senhas DRM
            for key, value in response.request.headers.items():
                k = key.lower()
                if k.startswith("x-") and k not in [
                    "x-requested-with",
                    "x-forwarded-for",
                ]:
                    self.drm_headers[key] = value

            if response.url in self.downloaded_files:
                return

            if response.url not in self.ordered_urls:
                self.ordered_urls.append(response.url)

            temp_filename = response.url.split("/")[-1]
            temp_filepath = os.path.join(self.output_dir, temp_filename)

            try:
                body = response.body()
                if not is_valid_image(body):
                    logging.warning(
                        f"  -> [!] Imagem {temp_filename} interceptada como HTML/Vazia. Passando para Pós-Processamento..."
                    )
                    return

                if is_valid_image(body):
                    with open(temp_filepath, "wb") as f:
                        f.write(body)
                    self.downloaded_files[response.url] = temp_filepath
                    logging.info(f"  -> [+] Imagem baixada: {temp_filename}")
                else:
                    logging.error(
                        f"  -> [-] Imagem {temp_filename} corrompida pela CDN."
                    )
            except Exception as e:
                logging.error(f"  -> [-] Falha ao salvar {temp_filename}: {e}")

    def rescue_missing_images_via_js(self, page):
        """Usa JS Blob e senhas DRM interceptadas para resgatar imagens perdidas."""
        import json
        import base64

        faltantes = [u for u in self.ordered_urls if u not in self.downloaded_files]
        if not faltantes:
            return

        logging.warning(
            f"  -> [!] {len(faltantes)} imagens perdidas detectadas. Iniciando resgate via JS Blob..."
        )
        page.wait_for_timeout(1500)

        headers_json = json.dumps(self.drm_headers) if self.drm_headers else "{}"

        for u in faltantes:
            try:
                b64 = page.evaluate(f"""async () => {{
                    const img = document.querySelector('img[src*="{u.split("/")[-1]}"]');
                    if (img && img.complete && img.naturalWidth > 0) {{
                        try {{
                            const canvas = document.createElement("canvas");
                            canvas.width = img.naturalWidth;
                            canvas.height = img.naturalHeight;
                            const ctx = canvas.getContext("2d");
                            ctx.drawImage(img, 0, 0);
                            const dataURL = canvas.toDataURL("image/jpeg", 1.0);
                            if (dataURL.length > 100) return dataURL;
                        }} catch(e) {{}}
                    }}
                    try {{
                        const drmHeaders = {headers_json};
                        const res = await fetch("{u}", {{ headers: drmHeaders }});
                        const blob = await res.blob();
                        return new Promise(resolve => {{
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        }});
                    }} catch(e) {{ return null; }}
                }}""")

                if b64 and "base64," in b64:
                    body = base64.b64decode(b64.split("base64,")[1])
                    if is_valid_image(body):
                        temp_filename = u.split("/")[-1]
                        temp_filepath = os.path.join(self.output_dir, temp_filename)
                        with open(temp_filepath, "wb") as f:
                            f.write(body)
                        self.downloaded_files[u] = temp_filepath
                        logging.info(
                            "  -> [+] Imagem resgatada com sucesso direto da Memória do Navegador!"
                        )
                    else:
                        logging.error(
                            "  -> [-] Imagem inacessível no momento (Rate Limit Persistente)."
                        )
            except Exception as e:
                logging.error(f"  -> [-] Falha na recuperação JS: {e}")

    def finalize_and_rename_images(self):
        """Renomeia os arquivos baixados garantindo a ordem pag_001.jpg."""
        logging.info(
            "[PIPELINE] Formatando e numerando as imagens no disco (pag_001.jpg)..."
        )
        for index, url in enumerate(self.ordered_urls):
            if url in self.downloaded_files:
                old_path = self.downloaded_files[url]
                new_filename = f"pag_{index + 1:03d}.jpg"
                new_path = os.path.join(self.output_dir, new_filename)
                if os.path.exists(old_path):
                    os.rename(old_path, new_path)
