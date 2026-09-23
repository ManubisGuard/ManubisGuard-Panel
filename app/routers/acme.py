from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.core.acme import AcmeHttp01ChallengeStore

router = APIRouter(tags=["ACME"])


@router.get("/.well-known/acme-challenge/{token}", include_in_schema=False)
async def acme_http01_challenge(token: str) -> PlainTextResponse:
    store = AcmeHttp01ChallengeStore()
    try:
        key_authorization = store.get(token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Challenge not found") from None

    if key_authorization is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    return PlainTextResponse(
        key_authorization,
        headers={"Cache-Control": "no-store"},
    )
