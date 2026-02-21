import { createClient } from "@/supabase/server"
import GlobalView from "./GlobalView"

export default async function GlobalPage() {
  const supabase = await createClient()

  const { data: tariffData } = await supabase
    .from("Country/Sector Tariff Probabilities")
    .select('country, "tariff risk pct"')

  return <GlobalView tariffData={tariffData ?? []} />
}
