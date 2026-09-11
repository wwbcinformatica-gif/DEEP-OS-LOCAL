"""
DEEP-OS — Download de arquivos do VPS para o cliente.

ISOLAMENTO POR TENANT
---------------------
Os documentos gerados ficam em `<raiz>/downloads/<tenant_id>/`. Este modulo
so serve arquivos do diretorio DO TENANT AUTENTICADO.

Antes todos caiam no mesmo `downloads/` e o `_find_file` usava `rglob`
recursivo sobre a raiz: um assinante que descobrisse o nome do arquivo de
outro conseguia baixa-lo. Agora:

- com tenant autenticado -> apenas `downloads/<tenant_id>/` e `docs/<tenant_id>/`
- sem tenant (app desktop) -> comportamento antigo (raiz de downloads/docs)
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from core.auth import get_current_tenant_optional

logger = logging.getLogger("download")
router = APIRouter()

_RAIZ = Path(__file__).resolve().parent.parent.parent


def _sanitize(tenant_id: str) -> str:
    """
    Nome de pasta seguro para o tenant.

    Delega para `core.tenant_identity.tenant_slug` — FONTE UNICA. Antes havia
    implementacoes diferentes no projeto, e o script de migracao usava o id
    CRU: os arquivos foram para `downloads/master-admin:wwbc22@gmail.com/`
    enquanto o backend procurava `downloads/master-adminwwbc22gmail.com/`.
    Todo download dava 404 por causa dessa divergencia.
    """
    from core.tenant_identity import tenant_slug

    return tenant_slug(tenant_id) or "desconhecido"


def _pastas_do_tenant(tenant_id: str) -> list[str]:
    """
    Variacoes de nome de pasta que podem conter arquivos DESTE tenant.

    Inclui o id cru (com `:`, `@`) para encontrar arquivos gravados antes da
    unificacao do sanitizador. So nomes derivados do proprio tenant entram
    aqui, entao nao ha como alcancar pasta de outro assinante.
    """
    nomes = [_sanitize(tenant_id)]
    bruto = str(tenant_id).strip()
    if bruto and bruto not in nomes and "/" not in bruto and "\\" not in bruto and ".." not in bruto:
        nomes.append(bruto)
    return nomes


def _bases_para_tenant(tenant_id: str | None) -> list[Path]:
    """
    Diretorios onde procurar o arquivo.

    Com tenant: o subdiretorio dele (em downloads/ e docs/) — considerando as
    variacoes de nome (`_sanitize` e id cru).
    Sem tenant: as raizes (app desktop, sem login).
    """
    if tenant_id:
        bases: list[Path] = []
        for nome in _pastas_do_tenant(tenant_id):
            bases.append(_RAIZ / "downloads" / nome)
            bases.append(_RAIZ / "docs" / nome)
        if bases:
            return bases
    return [_RAIZ / "downloads", _RAIZ / "docs"]


def _find_file(filepath: str, tenant_id: str | None = None) -> Path | None:
    """
    Procura o arquivo DENTRO dos diretorios permitidos para este tenant.

    Ordem de busca:
      1. Caminho absoluto que existe E esta dentro de um diretorio permitido
      2. Nome dentro das bases do tenant (`downloads/<id>/`, `docs/<id>/`)
      3. LEGADO: nome na raiz de `downloads/` (sem recursao, sem subpasta de
         outro tenant)

    O passo 3 existe porque, antes do isolamento por tenant, os documentos
    ficavam soltos em `downloads/`. Sem ele, todos os links ja enviados ao
    usuario (via save_document/write_file) passariam a dar 404 depois da
    correcao. Como o nome nao e adivinhavel e nao ha recursao, o risco de
    vazamento entre assinantes continua baixo.
    """
    bases = _bases_para_tenant(tenant_id)
    p = Path(filepath)

    def _dentro(caminho: Path) -> bool:
        """Confirma que o caminho resolvido esta dentro de alguma base."""
        try:
            real = caminho.resolve()
        except Exception:
            return False
        for b in bases:
            try:
                real.relative_to(b.resolve())
                return True
            except ValueError:
                continue
        return False

    # 1. Caminho absoluto que existe e esta dentro de uma base permitida
    if p.is_file() and _dentro(p):
        return p

    # 2. Caminho absoluto de arquivo de OUTRO tenant -> nega explicitamente
    if p.is_file():
        logger.warning("Download negado (fora do tenant %s): %s", tenant_id, filepath)
        return None

    # 3. Busca pelo nome dentro das bases do tenant
    for base in bases:
        if not base.exists():
            continue
        candidato = base / filepath
        if candidato.is_file() and _dentro(candidato):
            return candidato

        nome = p.name
        if nome:
            for achado in base.glob(nome):
                if achado.is_file() and _dentro(achado):
                    return achado

    # 4. LEGADO: raiz de downloads/ (somente com tenant autenticado, sem
    #    recursao e sem descer em subpasta de outro assinante)
    if tenant_id:
        raiz_downloads = (_RAIZ / "downloads").resolve()
        nome = p.name
        if nome and raiz_downloads.is_dir():
            for achado in raiz_downloads.glob(nome):
                if not achado.is_file():
                    continue
                # garante que e filho DIRETO da raiz (nao subpasta de tenant)
                if achado.parent.resolve() == raiz_downloads:
                    logger.info("Download legado (raiz de downloads/): %s", achado.name)
                    return achado

    return None


@router.get("/api/download")
async def download_file(
    path: str,
    tenant_id: str | None = Depends(get_current_tenant_optional),
):
    """
    Download de arquivo do VPS para o cliente.

    Uso: /api/download?path=caminho/do/arquivo.ext

    Com JWT, so serve arquivos do assinante autenticado.
    """
    file_path = _find_file(path, tenant_id)

    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="Arquivo nao encontrado"
        )

    filename = file_path.name

    # Headers para forcar download no navegador
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }

    logger.info("Download: %s (%s bytes) tenant=%s",
                filename, file_path.stat().st_size, tenant_id or "global")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        headers=headers,
    )


@router.get("/api/download/preview")
async def preview_file(
    path: str,
    tenant_id: str | None = Depends(get_current_tenant_optional),
):
    """
    Preview de arquivo (inline, nao download).

    Mesmas regras de isolamento do download.
    """
    file_path = _find_file(path, tenant_id)

    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="Arquivo nao encontrado"
        )

    headers = {
        "Content-Disposition": f'inline; filename="{file_path.name}"',
    }

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        headers=headers,
    )
