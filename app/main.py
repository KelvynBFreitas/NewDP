from fastapi.staticfiles import StaticFiles
from app.routes import auth_routes,dashboard_routes,cad_aprovador,cad_pj_vinculo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
app = FastAPI(
    docs_url=None,
    redoc_url=None#,
    #openapi_url=None
)

#app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(cad_aprovador.router)
app.include_router(cad_pj_vinculo.router)
#uvicorn app.main:app --reload






@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return HTMLResponse(content="""
            <html>
                <head><title>404 - Página não encontrada</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>😕 Ops! Página não encontrada.</h1>
                    <p>A URL que você tentou acessar não existe.</p>
                    <a href="/">Voltar para o início</a>
                </body>
            </html>
        """, status_code=404)
    return HTMLResponse(content=f"<h1>Erro {exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)

@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "message": "Erro interno no servidor. Já estamos verificando!",
            "detail": str(exc)
        }
    )
