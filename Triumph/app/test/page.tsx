import { createClient } from "../../supabase/server"

export default async function TestPage() {
  const supabase = await createClient()

  const { data, error } = await supabase
    .from("country_tariff_prob")
    .select("country, tariff_risk_pct")
    .limit(1)
    .single()

  if (error) {
    return (
      <div className="p-8">
        <h1 className="text-red-500 font-bold text-xl mb-2">Supabase Error</h1>
        <pre className="bg-red-50 text-red-800 p-4 rounded-lg text-sm">
          {JSON.stringify(error, null, 2)}
        </pre>
      </div>
    )
  }

  return (
    <div className="p-8">
      <h1 className="text-green-500 font-bold text-xl mb-4">✅ Supabase Connected!</h1>
      <p className="text-black text-lg">Country: <strong>{data.country}</strong></p>
      <p className="text-black text-lg">Tariff Risk: <strong>{data.tariff_risk_pct}</strong></p>
    </div>
  )
}