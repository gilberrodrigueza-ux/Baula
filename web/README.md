# baulashift.com

Página de presentación de Baula para la fase 0 (entrevistas). Sitio estático, sin dependencias ni paso de build: HTML, CSS y un poco de JS para cambiar entre español e inglés.

## Probar localmente

```bash
cd web
python3 -m http.server 8000
# abrir http://localhost:8000
```

## Publicar en Cloudflare (Workers con assets estáticos)

El `wrangler.jsonc` de la raíz del repo publica `web/` como assets estáticos del Worker `baula`.

1. Cloudflare → Workers & Pages → el Worker `baula` (conectado al repo, branch `main`). Cada push a `main` despliega solo.
2. Settings → Domains & Routes → Add → Custom domain → `baulashift.com`, y otra vez con `www.baulashift.com`. Como el dominio está en Cloudflare, los registros DNS se crean solos.

`web/.assetsignore` evita que este README quede publicado.

## Correo de contacto

El botón usa `hola@baulashift.com`. Para recibirlo sin servidor de correo: Cloudflare → el dominio → Email → Email Routing → reenviar `hola@` a tu buzón personal.
