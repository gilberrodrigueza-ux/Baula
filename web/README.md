# baulashift.com

Página de presentación de Baula para la fase 0 (entrevistas). Sitio estático, sin dependencias ni paso de build: HTML, CSS y un poco de JS para cambiar entre español e inglés.

## Probar localmente

```bash
cd web
python3 -m http.server 8000
# abrir http://localhost:8000
```

## Publicar con Cloudflare Pages

1. Cloudflare → Workers & Pages → Create → Pages → Connect to Git → repo `baula`.
2. Production branch: `main`. Framework preset: None. Build command: vacío. Build output directory: `web`.
3. En el proyecto de Pages → Custom domains → agregar `baulashift.com` y `www.baulashift.com`.
   Si el dominio está en Cloudflare, los registros DNS se crean solos. Si está en otro registrador, cambiar los nameservers a Cloudflare o crear un CNAME hacia `<proyecto>.pages.dev`.

## Correo de contacto

El botón usa `hola@baulashift.com`. Para recibirlo sin servidor de correo: Cloudflare → el dominio → Email → Email Routing → reenviar `hola@` a tu buzón personal.
