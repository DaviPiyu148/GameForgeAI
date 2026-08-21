import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.discovery import (
    BuildInspirationResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    MoreLikeThisRequest,
)
from app.services.discovery_service import DiscoveryService, discovery_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])


def get_discovery_service() -> DiscoveryService:
    """Dependency injector for singleton DiscoveryService."""
    return discovery_service


@router.post(
    "/search",
    response_model=DiscoverySearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search offline game catalog with Hybrid Retrieval (Lexical + Semantic + IGDB)",
    description="Deterministic hybrid discovery search combining full-catalog lexical token matching, SentenceTransformer FAISS vector similarity, and optional IGDB enrichment.",
)
async def search_games(
    request: DiscoverySearchRequest,
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoverySearchResponse:
    """
    Search the catalog of games using natural language descriptions, entity names, or concept phrases.
    """
    try:
        response = await service.search(request)
        return response
    except RuntimeError as re:
        logger.error(f"Discovery search runtime failure: {re}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery vector index is currently unavailable.",
        )
    except Exception as e:
        logger.error(f"Unexpected error during discovery search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the discovery search.",
        )


@router.get(
    "/similar/{steam_app_id}",
    response_model=DiscoverySearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Find games similar to a given Steam App ID",
    description="Retrieves nearest neighbors using the target game's semantic vector profile and tag/genre overlap.",
)
async def get_similar_games(
    steam_app_id: str,
    limit: int = Query(default=12, ge=1, le=50),
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoverySearchResponse:
    """
    Get recommendations similar to a seed game.
    """
    try:
        return await service.get_similar_games(steam_app_id=steam_app_id, limit=limit)
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
    except Exception as e:
        logger.error(f"Error fetching similar games for {steam_app_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve similar game recommendations.",
        )


@router.post(
    "/more-like-this",
    response_model=DiscoverySearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Multi-game recommendation pivot",
    description="Computes aggregate semantic profile over multiple game IDs and returns blended recommendations.",
)
async def more_like_this(
    request: MoreLikeThisRequest,
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoverySearchResponse:
    """
    Find games similar to a combined set of game IDs.
    """
    try:
        return await service.more_like_this(request)
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
    except Exception as e:
        logger.error(f"Error in more_like_this: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve more-like-this recommendations.",
        )


@router.get(
    "/build-inspiration/{steam_app_id}",
    response_model=BuildInspirationResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Game DNA inspiration for the /build compiler pipeline",
    description="Infers 2D prototype archetype, thematic presets, starter prompt, and recommended compiler parameters from a canonical game.",
)
async def get_build_inspiration(
    steam_app_id: str,
    service: DiscoveryService = Depends(get_discovery_service),
) -> BuildInspirationResponse:
    """
    Extract structured blueprint inspiration parameters from a discovered game.
    """
    try:
        return service.get_build_inspiration(steam_app_id)
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ke))
    except Exception as e:
        logger.error(f"Error in get_build_inspiration for {steam_app_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extract build inspiration.",
        )
