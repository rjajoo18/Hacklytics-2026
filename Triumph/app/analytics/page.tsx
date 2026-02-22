"use client"

import { useState, useRef, useEffect } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  IconBrain,
  IconSend,
  IconTrash,
  IconSnowflake,
  IconLoader2,
  IconUser,
  IconAlertCircle,
} from "@tabler/icons-react"
import { sendChatMessage } from "@/lib/api"

// Stable timestamp for SSR — avoids hydration mismatch
const BOOT_TIME = new Date()

// ── Types ──────────────────────────────────────────────────────────────────────

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

// ── Constants ──────────────────────────────────────────────────────────────────

const SUGGESTED_PROMPTS = [
  "Which countries have the highest tariff risk for the Energy sector?",
  "Compare tariff risk between China and Vietnam",
  "What sectors face the greatest supply chain disruption?",
  "Summarize tariff exposure for the Automotive sector",
  "Which country-sector pair has the lowest tariff risk?",
]

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi, I'm Quantara — your AI-powered supply chain risk analyst. I have access to live tariff risk data across all tracked countries and sectors. Ask me anything about tariff exposure, trade policy impact, or supply chain risk.",
  timestamp: BOOT_TIME,
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function generateId() {
  return Math.random().toString(36).slice(2, 10)
}

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user"

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full border ${
          isUser
            ? "bg-red-500/20 border-red-500/40"
            : "bg-blue-500/10 border-blue-500/20"
        }`}
      >
        {isUser ? (
          <IconUser className="size-4 text-red-400" />
        ) : (
          <IconSnowflake className="size-4 text-blue-400" />
        )}
      </div>

      {/* Bubble */}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? "bg-red-500/15 border border-red-500/20 text-foreground rounded-tr-sm"
              : "bg-white/5 border border-white/10 text-foreground rounded-tl-sm"
          }`}
        >
          {message.content}
        </div>
        <span suppressHydrationWarning className="text-[10px] text-muted-foreground px-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full border bg-blue-500/10 border-blue-500/20">
        <IconSnowflake className="size-4 text-blue-400 animate-spin" style={{ animationDuration: "3s" }} />
      </div>
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white/5 border border-white/10 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function handleSend(text?: string) {
    const prompt = (text ?? input).trim()
    if (!prompt || loading) return

    setInput("")
    setError(null)

    const userMsg: Message = {
      id: generateId(),
      role: "user",
      content: prompt,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const history = messages
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role, content: m.content }))

      const data = await sendChatMessage(prompt, history)

      if ("error" in data) {
        setError(data.error)
      } else {
        const assistantMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
        }
        setMessages((prev) => [...prev, assistantMsg])
      }
    } catch (err) {
      setError("Unexpected error. Check the browser console for details.")
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function clearHistory() {
    setMessages([WELCOME_MESSAGE])
    setError(null)
  }

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "calc(var(--spacing) * 72)",
          "--header-height": "calc(var(--spacing) * 12)",
        } as React.CSSProperties
      }
    >
      <div className="flex h-screen w-full overflow-hidden bg-background">
        <AppSidebar />

        <SidebarInset className="flex flex-col min-h-0 overflow-hidden">
          <SiteHeader />

          <div className="flex flex-1 min-h-0 flex-col gap-4 p-4 lg:p-6">
            {/* Page Header */}
            <div className="flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <IconBrain className="size-5 text-blue-400" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold">Analytics Chat</h1>
                  <p className="text-xs text-muted-foreground">
                    Powered by Snowflake Cortex · {" "}
                    <span className="text-blue-400">llama3.1-8b</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className="border-blue-500/30 text-blue-400 bg-blue-500/10 text-xs"
                >
                  <IconSnowflake className="size-3 mr-1" />
                  Snowflake Cortex
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearHistory}
                  className="text-muted-foreground hover:text-foreground h-8 gap-1.5"
                >
                  <IconTrash className="size-3.5" />
                  Clear
                </Button>
              </div>
            </div>

            {/* Chat Card */}
            <Card className="flex flex-col flex-1 min-h-0 border border-white/10 bg-card/60 backdrop-blur-sm overflow-hidden">
              <CardHeader className="border-b border-white/5 pb-3 flex-shrink-0">
                <CardTitle className="text-sm font-medium flex items-center gap-2 text-muted-foreground">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                  Quantara Risk Analyst
                  <span className="ml-auto text-[10px]">
                    {messages.length - 1} message{messages.length !== 2 ? "s" : ""}
                  </span>
                </CardTitle>
              </CardHeader>

              {/* Messages */}
              <CardContent className="flex flex-col flex-1 min-h-0 p-0">
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-thin scrollbar-thumb-white/10">
                  {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                  ))}
                  {loading && <TypingIndicator />}
                  <div ref={bottomRef} />
                </div>

                {/* Error Banner */}
                {error && (
                  <div className="mx-4 mb-3 flex items-start gap-2 px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                    <IconAlertCircle className="size-3.5 mt-0.5 flex-shrink-0" />
                    {error}
                  </div>
                )}

                {/* Suggested Prompts — only show when conversation is fresh */}
                {messages.length <= 1 && (
                  <div className="px-4 pb-3">
                    <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wider">
                      Suggested questions
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {SUGGESTED_PROMPTS.map((p) => (
                        <button
                          key={p}
                          onClick={() => handleSend(p)}
                          className="text-xs px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/10 hover:border-white/20 transition-colors text-left"
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Input Area */}
                <div className="border-t border-white/5 p-4">
                  <div className="flex gap-3 items-end">
                    <textarea
                      ref={inputRef}
                      rows={1}
                      value={input}
                      onChange={(e) => {
                        setInput(e.target.value)
                        // Auto-grow up to ~4 lines
                        e.target.style.height = "auto"
                        e.target.style.height = `${Math.min(e.target.scrollHeight, 112)}px`
                      }}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask about tariff risk, trade policy, or supply chain impact…"
                      disabled={loading}
                      className="flex-1 resize-none bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-blue-500/40 focus:bg-white/8 transition-colors disabled:opacity-50 min-h-[44px] max-h-28 overflow-y-auto"
                      style={{ height: "44px" }}
                    />
                    <Button
                      onClick={() => handleSend()}
                      disabled={loading || !input.trim()}
                      size="icon"
                      className="flex-shrink-0 w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-500/30 text-blue-400 hover:bg-blue-500/30 hover:text-blue-300 disabled:opacity-40 transition-colors"
                    >
                      {loading ? (
                        <IconLoader2 className="size-4 animate-spin" />
                      ) : (
                        <IconSend className="size-4" />
                      )}
                    </Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-2">
                    Press <kbd className="px-1 py-0.5 rounded bg-white/10 font-mono text-[9px]">Enter</kbd> to send ·{" "}
                    <kbd className="px-1 py-0.5 rounded bg-white/10 font-mono text-[9px]">Shift+Enter</kbd> for new line
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  )
}
