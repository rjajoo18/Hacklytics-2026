import { createClient } from "@/supabase/server"
import GlobalView from "./GlobalView"

export default async function GlobalPage() {
  const supabase = await createClient()

  const { data: tariffData } = await supabase
    .from("country_tariff_prob")
    .select("country, tariff_risk_pct")

  const { data: sectorData } = await supabase
    .from("country_tariff_prob")
    .select("country, sector, tariff_risk_prob")

  return <GlobalView tariffData={tariffData ?? []} sectorData={sectorData ?? []} />
}