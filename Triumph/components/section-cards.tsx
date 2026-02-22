import { IconTrendingDown, IconTrendingUp, IconWorld, IconBuildingFactory2, IconCash, IconScale, IconBrain, IconAlertTriangle, IconCurrencyDollar, IconChartBar } from "@tabler/icons-react"
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

interface SectionCardsProps {
  tariffProb?: number | null
  tariffProbLoading?: boolean
}

export function SectionCards({ tariffProb, tariffProbLoading }: SectionCardsProps) {
  return (
    <div className="grid grid-cols-1 gap-3 px-4 lg:px-6 lg:grid-cols-3">
      
      {/* Big Tariff Prediction Box */}
      <Card className="relative overflow-hidden border border-red-500/30 bg-gradient-to-br from-red-950/30 to-card shadow-md row-span-2 flex flex-col">
        <div className="absolute top-0 right-0 w-48 h-48 bg-red-500/10 rounded-full -translate-y-16 translate-x-16 blur-2xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-red-500/5 rounded-full translate-y-12 -translate-x-12 blur-xl pointer-events-none" />
        <CardHeader className="pb-2">
          <div className="flex items-center gap-1.5 text-red-400">
            <IconBrain className="size-4" />
            <CardDescription className="text-red-400 font-medium">Tariff Prediction</CardDescription>
          </div>
          <CardTitle className="text-5xl font-bold tabular-nums text-red-500 mt-2">
            {tariffProbLoading
              ? "…"
              : tariffProb != null
              ? `${tariffProb.toFixed(1)}%`
              : "—"}
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="text-xs border-red-500/40 text-red-400 bg-red-500/10">
              AI Confidence
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-3 text-sm flex-1 justify-end">
          <div className="w-full">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Prediction Model Accuracy</span>
              <span className="text-red-400 font-medium">61%</span>
            </div>
            <div className="w-full h-1.5 bg-muted/40 rounded-full overflow-hidden">
              <div className="h-full bg-red-500 rounded-full" style={{ width: "61%" }} />
            </div>
          </div>
          <div className="w-full">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">Stock Market Fluctuations</span>
              <span className="text-orange-400 font-medium">72%</span>
            </div>
            <div className="w-full h-1.5 bg-muted/40 rounded-full overflow-hidden">
              <div className="h-full bg-orange-500 rounded-full" style={{ width: "72%" }} />
            </div>
          </div>

          <div className="pt-2 border-t border-border/30 w-full">
            <p className="text-xs text-muted-foreground">
              Model predicts further escalation within <span className="text-red-400 font-medium">60 days</span> based on current trade flow data.
            </p>
          </div>
        </CardFooter>
      </Card>

      {/* Right 4 boxes */}
      <Card className="@container/card relative overflow-hidden border border-border/40 bg-card shadow-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <IconCurrencyDollar className="size-3.5" />
            <CardDescription>Trade Deficit</CardDescription>
          </div>
          <CardTitle className="text-3xl font-bold tabular-nums text-red-500">
            $1.2T
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="text-xs">
              <IconTrendingDown className="size-3" />
              -8.3%
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-xs pt-0">
          <div className="font-medium">Annual US trade deficit</div>
          <div className="text-muted-foreground">Compared to x country</div>
        </CardFooter>
      </Card>

      <Card className="@container/card relative overflow-hidden border border-border/40 bg-card shadow-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <IconChartBar className="size-3.5" />
            <CardDescription>Foreign Exchange</CardDescription>
          </div>
          <CardTitle className="text-3xl font-bold tabular-nums text-red-500">
            7.24
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="text-xs">
              <IconTrendingUp className="size-3" />
              CNY/USD
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-xs pt-0">
          <div className="font-medium">Currency decline/increase</div>
          <div className="text-muted-foreground">Change in exchange impact</div>
        </CardFooter>
      </Card>

      <Card className="@container/card relative overflow-hidden border border-border/40 bg-card shadow-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <IconAlertTriangle className="size-3.5" />
            <CardDescription>Market Fluctuations</CardDescription>
          </div>
          <CardTitle className="text-3xl font-bold tabular-nums text-red-500">
            High
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="text-xs border-red-500/30 text-red-400">
              Level 4/5
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-xs pt-0">
          <div className="font-medium">Elevated geopolitical tension</div>
          <div className="text-muted-foreground">Taiwan strait concerns</div>
        </CardFooter>
      </Card>

      <Card className="@container/card relative overflow-hidden border border-border/40 bg-card shadow-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <IconWorld className="size-3.5" />
            <CardDescription>Market Size</CardDescription>
          </div>
          <CardTitle className="text-3xl font-bold tabular-nums text-red-500">
            $18.4T
          </CardTitle>
          <CardAction>
            <Badge variant="outline" className="text-xs">
              <IconTrendingDown className="size-3" />
              -3.2%
            </Badge>
          </CardAction>
        </CardHeader>
        <CardFooter className="flex-col items-start gap-1 text-xs pt-0">
          <div className="font-medium">Affected trade market cap</div>
          <div className="text-muted-foreground">Across all tariffed goods</div>
        </CardFooter>
      </Card>

    </div>
  )
}