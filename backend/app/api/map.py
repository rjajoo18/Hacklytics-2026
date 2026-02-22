"""
Map page API router.

Endpoints
---------
GET /api/map/country-sectors?country=...
    Returns all sectors and their tariff probabilities for a given country.
    Source table: country_tariff_prob
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from ..core.supabase import get_supabase
from ..models.responses import CountrySectorsResponse, SectorProbability

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/country-sectors", response_model=CountrySectorsResponse)
async def get_country_sectors(
    country: str    = Query(..., description="Country name (e.g. 'Germany')"),
    supabase: Client = Depends(get_supabase),
) -> CountrySectorsResponse:
    """
    Return all sectors and their tariff probability % for a given country.

    Results are sorted alphabetically by sector.
    """
    resp = (
        supabase.table("country_tariff_prob")
        .select("sector, tariff_risk_prob")
        .eq("country", country)
        .order("sector", desc=False)
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No sector data found for country='{country}' in country_tariff_prob. "
                "Check that the country name matches rows in the table."
            ),
        )

    sectors = [
        SectorProbability(
            sector=row["sector"],
            # tariff_risk_prob is stored as 0–1 float; convert to percentage
            probability_percent=round(float(row["tariff_risk_prob"]) * 100, 2),
        )
        for row in resp.data
    ]

    return CountrySectorsResponse(country=country, sectors=sectors)
