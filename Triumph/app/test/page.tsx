import { createClient } from "../../supabase/server"

export default async function TestPage() {
  const supabase = await createClient()

  const { data, error } = await supabase
    .from("Country/Sector Tariff Probabilities")
    .select("*")
    .limit(1)

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
      <pre className="bg-gray-100 text-black p-4 rounded-lg text-sm overflow-auto">
        {data && data.length > 0 ? JSON.stringify(data[0], null, 2) : "No rows returned"}
      </pre>
    </div>
  )
}